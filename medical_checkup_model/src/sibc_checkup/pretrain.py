"""자기지도 사전학습 (구축가이드 v1.3, 7.4절).

- 입력: SiBC 수집 가능 5채널의 일별 시계열 14일 창
  [step_count, heartrate_median, heartrate_rest, sleep_duration_min, spo2_median]
- 데이터: 자체 무라벨 일별 데이터 + LifeSnaps (동일 채널·단위)
- 목표: 마스킹 복원(masked reconstruction) — 무작위로 가린 날의 값을 복원
- 산출: 인코더 가중치 + 사용자 임베딩 (01_Results/pretrain/)
- 주의: 사전학습 자체는 성능 주장을 만들지 않는다 (복원 손실만 보고).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from .env import PROJECT_ROOT

CHANNELS = ["step_count", "heartrate_median", "heartrate_rest",
            "sleep_duration_min", "spo2_median"]
WINDOW_DAYS = 14
EMB_DIM = 16
OUT_DIR = PROJECT_ROOT / "01_Results" / "pretrain"


def build_sequences(daily: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str], dict]:
    """일별 long -> (N, 14, C) 창 배열 + 관측 마스크. z-정규화 통계는 저장한다."""
    wide = (daily.pivot_table(index=["user_key", "d"], columns="feature",
                              values="value", aggfunc="median")
            .reindex(columns=CHANNELS).reset_index())
    stats = {}
    for c in CHANNELS:
        mu, sd = float(wide[c].mean()), float(wide[c].std() or 1.0)
        stats[c] = {"mean": mu, "std": sd}
        wide[c] = (wide[c] - mu) / sd

    xs, ms, owners = [], [], []
    for user, g in wide.groupby("user_key"):
        g = g.set_index("d").sort_index()
        idx = pd.date_range(g.index.min(), g.index.max(), freq="D")
        arr = g.reindex(idx)[CHANNELS].to_numpy(dtype=np.float32)
        for start in range(0, len(arr) - WINDOW_DAYS + 1, 7):  # 7일 스트라이드
            win = arr[start:start + WINDOW_DAYS]
            mask = ~np.isnan(win)
            if mask.any(axis=1).sum() >= 7:  # 최소 7일 관측
                xs.append(np.nan_to_num(win))
                ms.append(mask.astype(np.float32))
                owners.append(user)
    return np.stack(xs), np.stack(ms), owners, stats


class MaskedEncoder(nn.Module):
    def __init__(self, n_ch: int = len(CHANNELS), emb: int = EMB_DIM):
        super().__init__()
        self.gru = nn.GRU(input_size=n_ch * 2, hidden_size=32, batch_first=True)
        self.to_emb = nn.Linear(32, emb)
        self.decoder = nn.Sequential(
            nn.Linear(emb, 64), nn.ReLU(), nn.Linear(64, WINDOW_DAYS * n_ch))

    def encode(self, x, mask):
        inp = torch.cat([x * mask, mask], dim=-1)
        _, h = self.gru(inp)
        return self.to_emb(h[-1])

    def forward(self, x, mask):
        z = self.encode(x, mask)
        rec = self.decoder(z).view(x.shape)
        return z, rec


def pretrain(epochs: int = 30, mask_frac: float = 0.3, seed: int = 42) -> dict:
    from .features_own import fetch_daily_features
    from .lifesnaps import load_daily

    daily = pd.concat([fetch_daily_features(), load_daily()], ignore_index=True)
    daily = daily[daily["feature"].isin(CHANNELS)]
    x_np, m_np, owners, stats = build_sequences(daily)

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    x = torch.from_numpy(x_np)
    m = torch.from_numpy(m_np)
    model = MaskedEncoder()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)

    n = len(x)
    losses = []
    for epoch in range(epochs):
        perm = torch.from_numpy(rng.permutation(n))
        total = 0.0
        for i in range(0, n, 256):
            idx = perm[i:i + 256]
            xb, mb = x[idx], m[idx]
            drop = torch.from_numpy(
                (rng.random(mb.shape) < mask_frac).astype(np.float32))
            vis = mb * (1 - drop)          # 입력에 보여줄 관측
            hidden = mb * drop             # 복원 대상 (관측인데 가린 것)
            _, rec = model(xb, vis)
            loss = ((rec - xb) ** 2 * hidden).sum() / hidden.sum().clamp(min=1)
            opt.zero_grad(); loss.backward(); opt.step()
            total += float(loss) * len(idx)
        losses.append(round(total / n, 4))

    # 사용자 임베딩: 창 임베딩의 사용자별 평균
    model.eval()
    with torch.no_grad():
        z = model.encode(x, m).numpy()
    emb = pd.DataFrame(z, columns=[f"ssl_emb_{i}" for i in range(EMB_DIM)])
    emb["user_key"] = owners
    user_emb = emb.groupby("user_key").mean().reset_index()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), OUT_DIR / "encoder.pt")
    user_emb.to_parquet(OUT_DIR / "user_embeddings.parquet", index=False)
    report = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "windows": int(n),
        "users": int(user_emb.shape[0]),
        "users_own": int(sum(not u.startswith("lifesnaps_") for u in user_emb["user_key"])),
        "users_lifesnaps": int(sum(u.startswith("lifesnaps_") for u in user_emb["user_key"])),
        "channels": CHANNELS,
        "loss_first_last": [losses[0], losses[-1]],
        "note": "복원 손실은 임베딩 학습 진행도 지표일 뿐 검진 예측 성능이 아님",
    }
    with open(OUT_DIR / "pretrain_report.json", "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(OUT_DIR / "norm_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    return report
