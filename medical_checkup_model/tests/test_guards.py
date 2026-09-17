"""읽기 전용 가드와 가중치 상한."""
import pandas as pd
import pytest

from sibc_checkup.db import guard_sql
from sibc_checkup.unified import _weights, load_policy


def test_sql_guard_allows_select():
    guard_sql("SELECT 1")
    guard_sql("  WITH x AS (SELECT 1) SELECT * FROM x")


@pytest.mark.parametrize("sql", [
    "INSERT INTO t VALUES (1)", "UPDATE t SET a=1", "DELETE FROM t",
    "DROP TABLE t", "TRUNCATE t",
])
def test_sql_guard_blocks_writes(sql):
    with pytest.raises(PermissionError):
        guard_sql(sql)


def test_own_weight_cap():
    cap = float(load_policy()["joint_training"]["own_weight_cap_initial"])
    df = pd.DataFrame({"source": ["own"] * 10 + ["nhanes"] * 990})
    w = _weights(df)
    own_share = w[df["source"] == "own"].sum() / w.sum()
    assert own_share <= cap + 0.01
    assert (w[df["source"] == "own"] >= 1.0).all()
