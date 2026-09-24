"""Tests for image_rules (v0.1). Uses local temp PNGs -> fully offline."""

from PIL import Image

from backend.app.image_rules import check_image, check_image_list


def _make_png(path, size=(975, 1300), fmt="PNG", color=(255, 255, 255)):
    img = Image.new("RGB", size, color)
    img.save(path, fmt)
    return str(path)


class TestCheckImage:
    def test_optimal_resolution_ok(self, tmp_path):
        p = _make_png(tmp_path / "good.png", (975, 1300))
        r = check_image(p)
        assert r.ok is True
        assert r.errors == []

    def test_min_resolution_ok(self, tmp_path):
        p = _make_png(tmp_path / "min.png", (200, 250))
        r = check_image(p)
        assert r.ok is True
        # not optimal -> warning only
        assert any("optimal" in w for w in r.warnings)

    def test_max_resolution_ok(self, tmp_path):
        p = _make_png(tmp_path / "max.png", (3520, 4400))
        r = check_image(p)
        assert r.ok is True

    def test_square_ratio_error(self, tmp_path):
        p = _make_png(tmp_path / "sq.png", (1000, 1000))
        r = check_image(p)
        assert r.ok is False
        assert any("ratio" in e for e in r.errors)

    def test_too_small_error(self, tmp_path):
        p = _make_png(tmp_path / "tiny.png", (100, 100))
        r = check_image(p)
        assert r.ok is False
        assert any("resolution" in e for e in r.errors)

    def test_bad_format_error(self, tmp_path):
        # GIF is not in the allowed whitelist
        p = tmp_path / "anim.gif"
        Image.new("RGB", (975, 1300), (255, 255, 255)).save(p, "GIF")
        r = check_image(str(p))
        assert r.ok is False
        assert any("format" in e for e in r.errors)


class TestCheckImageList:
    def test_no_images_error(self):
        res = check_image_list([])
        assert res["ok"] is False
        assert any("too few" in e for e in res["errors"])

    def test_ok_list(self, tmp_path):
        paths = [_make_png(tmp_path / f"g{i}.png") for i in range(3)]
        res = check_image_list(paths)
        assert res["ok"] is True
        assert res["count"] == 3

    def test_too_many_error(self, tmp_path):
        paths = [_make_png(tmp_path / f"m{i}.png") for i in range(16)]
        res = check_image_list(paths)
        assert res["ok"] is False
        assert any("too many" in e for e in res["errors"])
