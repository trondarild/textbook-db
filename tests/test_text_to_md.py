"""Tests for text_to_md plugin loader and registry parameter pass-through."""

import pathlib
import sys
import types

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from text_to_md import load_plugin, apply_hook


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plugin(**hooks):
    """Build an in-memory module with the given hook functions."""
    mod = types.ModuleType('fake_plugin')
    for name, fn in hooks.items():
        setattr(mod, name, fn)
    return mod


def _segs(n=3):
    return [{'pdf_page': i, 'book_page': i, 'text': f'Page {i}.'} for i in range(1, n + 1)]


# ---------------------------------------------------------------------------
# load_plugin
# ---------------------------------------------------------------------------

class TestLoadPlugin:
    def test_returns_none_for_missing_plugin(self, tmp_path, monkeypatch):
        monkeypatch.setattr('text_to_md.PLUGINS_DIR', tmp_path)
        assert load_plugin('no_such_book') is None

    def test_loads_existing_plugin(self, tmp_path, monkeypatch):
        monkeypatch.setattr('text_to_md.PLUGINS_DIR', tmp_path)
        plugin_file = tmp_path / 'mybook.py'
        plugin_file.write_text('LOADED = True\n')
        mod = load_plugin('mybook')
        assert mod is not None
        assert mod.LOADED is True

    def test_plugin_can_define_hooks(self, tmp_path, monkeypatch):
        monkeypatch.setattr('text_to_md.PLUGINS_DIR', tmp_path)
        (tmp_path / 'mybook.py').write_text(
            'def post_segment(segs, meta): return segs[:1]\n'
        )
        mod = load_plugin('mybook')
        result = mod.post_segment(_segs(3), {})
        assert len(result) == 1


# ---------------------------------------------------------------------------
# apply_hook
# ---------------------------------------------------------------------------

class TestApplyHook:
    def test_no_plugin_returns_segments_unchanged(self):
        segs = _segs(3)
        result = apply_hook(None, 'post_segment', segs, {})
        assert result is segs

    def test_missing_hook_returns_segments_unchanged(self):
        plugin = _make_plugin()  # no hooks defined
        segs = _segs(3)
        result = apply_hook(plugin, 'post_segment', segs, {})
        assert result is segs

    def test_hook_is_called_with_segments_and_meta(self):
        received = {}

        def hook(segs, meta):
            received['segs'] = segs
            received['meta'] = meta
            return segs

        plugin = _make_plugin(post_segment=hook)
        segs = _segs(2)
        meta = {'title': 'Test'}
        apply_hook(plugin, 'post_segment', segs, meta)
        assert received['segs'] is segs
        assert received['meta'] is meta

    def test_hook_return_value_is_used(self):
        def hook(segs, meta):
            return segs[:1]  # drop all but first

        plugin = _make_plugin(post_segment=hook)
        result = apply_hook(plugin, 'post_segment', _segs(3), {})
        assert len(result) == 1

    def test_post_strip_hook_called(self):
        called = []

        def hook(segs, meta):
            called.append(True)
            return segs

        plugin = _make_plugin(post_strip=hook)
        apply_hook(plugin, 'post_strip', _segs(2), {})
        assert called

    def test_different_hooks_are_independent(self):
        log = []
        plugin = _make_plugin(
            post_segment=lambda s, m: (log.append('seg'), s)[1],
            post_annotate=lambda s, m: (log.append('ann'), s)[1],
        )
        apply_hook(plugin, 'post_segment', _segs(1), {})
        apply_hook(plugin, 'post_strip', _segs(1), {})   # not defined — no-op
        apply_hook(plugin, 'post_annotate', _segs(1), {})
        assert log == ['seg', 'ann']


# ---------------------------------------------------------------------------
# Registry parameter pass-through (integration-level: no real files needed)
# ---------------------------------------------------------------------------

class TestRegistryParams:
    def test_header_stripper_kwargs_forwarded(self, tmp_path, monkeypatch):
        """strip_headers should receive kwargs from meta['header_stripper']."""
        captured = {}

        def fake_strip(segs, **kwargs):
            captured.update(kwargs)
            return segs, frozenset()

        monkeypatch.setattr('text_to_md.strip_headers', fake_strip)
        monkeypatch.setattr('text_to_md.segment', lambda t: _segs(2))
        monkeypatch.setattr('text_to_md.annotate_segments', lambda s: s)
        monkeypatch.setattr('text_to_md.write_md', lambda s, m, p: pathlib.Path(p).touch())
        monkeypatch.setattr('text_to_md.PLUGINS_DIR', tmp_path / 'plugins')
        monkeypatch.setattr('text_to_md.MD_DIR', tmp_path / 'md')
        (tmp_path / 'md').mkdir()

        import text_to_md
        txt = tmp_path / 'book.txt'
        txt.write_text('dummy')
        meta = {
            'text': str(txt),
            'header_stripper': {'global_thresh': 0.20, 'window_size': 15},
        }
        text_to_md.convert_book('testbook', meta, force=True)

        assert captured.get('global_thresh') == 0.20
        assert captured.get('window_size') == 15
