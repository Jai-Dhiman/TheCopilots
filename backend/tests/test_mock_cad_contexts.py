import math

import pytest

from models.mock_cad_contexts import get_desk_mock
from models.freecad_client import FreecadClient


class TestTableMockStructure:
    def test_has_required_keys(self):
        mock = get_desk_mock()
        for key in ("document_name", "objects", "sketches", "materials", "bounding_box"):
            assert key in mock, f"Missing key: {key}"

    def test_has_tabletop_holes_legs_and_bosses(self):
        mock = get_desk_mock()
        objects = mock["objects"]
        # 1 tabletop + 4 holes + 4 legs + 4 bosses = 13
        assert len(objects) == 13
        names = [o["name"] for o in objects]
        assert "Tabletop" in names
        for corner in ("FL", "FR", "BL", "BR"):
            assert f"Hole_{corner}" in names
            assert f"Leg_{corner}" in names
            assert f"Boss_{corner}" in names

    def test_dimensions_are_plausible(self):
        mock = get_desk_mock()
        for obj in mock["objects"]:
            assert obj["volume_mm3"] > 0
            assert obj["surface_area_mm2"] > 0
            bb = obj["bounding_box"]
            assert bb["x_max"] > bb["x_min"]
            assert bb["y_max"] > bb["y_min"]
            assert bb["z_max"] > bb["z_min"]

    def test_tabletop_dimensions(self):
        mock = get_desk_mock()
        tabletop = mock["objects"][0]
        assert tabletop["name"] == "Tabletop"
        dims = tabletop["dimensions"]
        assert dims["length"] == 700.0
        assert dims["width"] == 350.0
        assert dims["height"] == 50.0

    def test_hole_dimensions(self):
        mock = get_desk_mock()
        holes = [o for o in mock["objects"] if o["name"].startswith("Hole_")]
        assert len(holes) == 4
        for hole in holes:
            dims = hole["dimensions"]
            assert dims["diameter"] == 60.0
            assert dims["depth"] == 50.0
            assert hole["type"] == "PartDesign::Pocket"
            assert hole["parent"] == "Tabletop"

    def test_leg_dimensions(self):
        mock = get_desk_mock()
        legs = [o for o in mock["objects"] if o["name"].startswith("Leg_")]
        assert len(legs) == 4
        for leg in legs:
            dims = leg["dimensions"]
            assert dims["diameter"] == 100.0
            assert dims["height"] == 700.0
            expected_vol = math.pi * 50.0**2 * 700.0
            assert abs(leg["volume_mm3"] - expected_vol) < 0.5

    def test_boss_dimensions(self):
        mock = get_desk_mock()
        bosses = [o for o in mock["objects"] if o["name"].startswith("Boss_")]
        assert len(bosses) == 4
        for boss in bosses:
            dims = boss["dimensions"]
            assert dims["diameter"] == 60.0
            assert dims["height"] == 50.0
            expected_vol = math.pi * 30.0**2 * 50.0
            assert abs(boss["volume_mm3"] - expected_vol) < 0.5

    def test_boss_parent_is_corresponding_leg(self):
        mock = get_desk_mock()
        bosses = [o for o in mock["objects"] if o["name"].startswith("Boss_")]
        for boss in bosses:
            corner = boss["name"].split("_")[1]
            assert boss["parent"] == f"Leg_{corner}"

    def test_sketches_have_geometry(self):
        mock = get_desk_mock()
        sketches = mock["sketches"]
        assert len(sketches) == 4
        for sketch in sketches:
            assert len(sketch["geometry"]) > 0
            assert sketch["constraint_count"] > 0

    def test_materials_present(self):
        mock = get_desk_mock()
        assert len(mock["materials"]) == 1
        assert mock["materials"][0]["material"] == "Birch Plywood"

    def test_bounding_box_encloses_all_objects(self):
        mock = get_desk_mock()
        bb = mock["bounding_box"]
        for obj in mock["objects"]:
            obj_bb = obj["bounding_box"]
            assert obj_bb["x_min"] >= bb["x_min"]
            assert obj_bb["x_max"] <= bb["x_max"]
            assert obj_bb["y_min"] >= bb["y_min"]
            assert obj_bb["y_max"] <= bb["y_max"]
            assert obj_bb["z_min"] >= bb["z_min"]
            assert obj_bb["z_max"] <= bb["z_max"]


class TestFreecadClientMockMode:
    @pytest.mark.asyncio
    async def test_health_check_returns_true_in_mock_mode(self):
        client = FreecadClient()
        client._mock_mode = True
        assert await client.health_check() is True

    @pytest.mark.asyncio
    async def test_extract_returns_table_mock_in_mock_mode(self):
        client = FreecadClient()
        client._mock_mode = True
        result = await client.extract_cad_context()
        assert result["document_name"] == "Table_Model"
        assert len(result["objects"]) == 13
        assert len(result["sketches"]) == 4

    @pytest.mark.asyncio
    async def test_mock_mode_is_false_by_default(self):
        client = FreecadClient()
        assert client._mock_mode is False
