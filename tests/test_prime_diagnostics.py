import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parent))
from support import load_integration_module
mod=load_integration_module("prime_diagnostics")
local=load_integration_module("local_source")


class PrimeDiagnosticsTests(unittest.TestCase):
    def test_every_reported_leaf_has_a_row(self):
        raw={"102":'{"L":[2290,0,0],"p":0,"e":0,"t":360,"d":0,"c":0,"s":0,"p3":0}',
             "117":'{"L1":[2270,0],"L2":[0,0],"L3":[0,0],"cp":61,"gd":667,"dpn":41}',
             "151":'{"m":0,"c":32}',"112":"secret-card", "113":"secret-auth","999":42,"140":False}
        rows=mod.readable_rows(local.public_dps(raw))
        keys={(r["dp"],r["path"]) for r in rows}
        self.assertIn(("102","L[2]"),keys)
        self.assertIn(("117","L3[1]"),keys)
        self.assertIn(("117","gd"),keys)
        self.assertIn(("151","c"),keys)
        self.assertIn(("999",""),keys)
        self.assertNotIn("secret",json.dumps(rows))
        cp=next(r for r in rows if r["dp"]=="117" and r["path"]=="cp")
        self.assertEqual(cp["value"],6.1)
        self.assertEqual(cp["unit"],"V")
        current=next(r for r in rows if r["dp"]=="117" and r["path"]=="L1[1]")
        self.assertEqual(current["unit"],"")
        self.assertEqual(current["note"],mod.UNKNOWN)
        self.assertEqual(current["group"], "technical")
        self.assertEqual(current["label"]["pl"], "DP117 · L1[1]")
        self.assertNotIn("niepotwierdzone", json.dumps(rows, ensure_ascii=False))

    def test_technical_values_keep_raw_value_without_guessed_scale(self):
        rows = mod.readable_rows({"117": '{"L1":[2270,0],"cp":61}', "154": False})
        voltage = next(row for row in rows if row["path"] == "L1[0]")
        self.assertEqual(voltage["value"], 2270)
        self.assertEqual(voltage["unit"], "")
        self.assertEqual(voltage["group"], "technical")
        cp = next(row for row in rows if row["path"] == "cp")
        self.assertEqual(cp["group"], "electrical")

    def test_false_zero_and_unknown_are_not_discarded(self):
        rows=mod.readable_rows({"140":False,"150":0,"999":{},"154":False})
        self.assertEqual(len(rows),4)
        self.assertFalse(next(r for r in rows if r["dp"]=="140")["value"])
        self.assertEqual(next(r for r in rows if r["dp"]=="154")["note"],mod.UNKNOWN)
