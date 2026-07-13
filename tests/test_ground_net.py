import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from ground_net import Station, plan, ANSWER

def test_plan():
    r = plan([Station("a", True, 10, 60)], 50)
    assert r["ok"] and r["answer"]==ANSWER

def test_fail():
    r = plan([Station("a", True, 5, 100)], 50)
    assert r["ok"] is False

if __name__=="__main__":
    test_plan(); test_fail(); print("ok")
