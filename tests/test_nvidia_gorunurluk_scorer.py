"""Kamera görünürlük puanlayıcısı model çağrısı yapmadan sınanır."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.puanla_nvidia_gorunurluk import puanla


def olay(kod):
    return {
        "time": "00:00", "event": kod, "severity": "Yüksek",
        "category": "Kaza", "region": None, "isg_kod": kod,
        "isg_slot": "slot", "isg_deger": "VAR",
    }


manifest = {"rows": [
    {"path": "data/dev/Fire/a.mp4", "scenario": "fire",
     "run_id": "fire_run", "camera": "cam_0"},
    {"path": "data/dev/Road/b.mp4", "scenario": "nearmiss",
     "run_id": "near_run", "camera": "cam_0"},
    {"path": "data/dev/Normal/c.mp4", "scenario": "box_pickup",
     "run_id": "normal_run", "camera": "cam_0"},
]}
visibility = {
    "scenario_code": {
        "fire": "Warehouse_Visible_Fire",
        "forklift_collision": "Forklift_Shelf_Collision",
        "nearmiss": "Forklift_Human_NearMiss",
    },
    "visible_cameras_by_run": {
        "fire_run": ["cam_0"], "near_run": ["cam_0"], "normal_run": [],
    },
    "normal_scenarios": ["box_pickup"],
}
result = {"rows": [
    {"path": "data/dev/Fire/a.mp4", "events": [olay("Warehouse_Visible_Fire")],
     "n_events": 1, "max_severity": 4, "risk_ord": 4, "risk_level": "Kritik",
     "triggered": [], "summary": "Duman var"},
    {"path": "data/dev/Road/b.mp4", "events": [olay("Forklift_Human_NearMiss")],
     "n_events": 1, "max_severity": 3, "risk_ord": 3, "risk_level": "Yüksek",
     "triggered": [], "summary": "Ramak kala"},
    {"path": "data/dev/Normal/c.mp4", "events": [], "n_events": 0,
     "max_severity": 0, "risk_ord": 1, "risk_level": "Düşük",
     "triggered": [], "summary": "Rutin kutu alma"},
]}

score = puanla(result, manifest, visibility)
assert score["n_views"] == 3
assert score["recall_by_code"]["Warehouse_Visible_Fire"]["k"] == 1
assert score["recall_by_code"]["Forklift_Human_NearMiss"]["k"] == 1
assert score["false_positive_by_code"]["Forklift_Shelf_Collision"]["k"] == 0
assert score["normal"]["dispatch_fp"]["k"] == 0
assert score["acceptance"]["pass"] is True

# Odak kosusu farkli kokte hard-link tutabilir; acik alt-kume kipinde yalniz
# benzersiz dosya adi eslesir ve rapor bunu gorunur bicimde isaretler.
subset = puanla({"rows": [{**result["rows"][1],
                            "path": "data/focus/RoadAccidents/b.mp4"}]},
                manifest, visibility, allow_subset=True)
assert subset["subset"] is True
assert subset["n_views"] == 1
assert subset["recall_by_code"]["Forklift_Human_NearMiss"]["k"] == 1
collision_only = puanla(result, manifest, visibility,
                        codes=["Forklift_Shelf_Collision"])
assert collision_only["codes"] == ["Forklift_Shelf_Collision"]
assert set(collision_only["recall_by_code"]) == {"Forklift_Shelf_Collision"}
print("gecen=11 kalan=0")
