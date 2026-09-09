"""Tests for the PawUI CLI."""

import json

import pytest

from pawui.cli import check, main, render, run, schema_cmd


class TestCLI:
    def test_main_help(self, capsys):
        assert main(["--help"]) == 0
        out = capsys.readouterr().out
        assert "PawUI" in out
        assert "用法" in out or "Usage" in out

    def test_main_version(self, capsys):
        assert main(["--version"]) == 0
        out = capsys.readouterr().out
        assert "PawUI" in out

    def test_main_no_args(self, capsys):
        assert main([]) == 2
        out = capsys.readouterr().err
        assert "用法" in out or "Usage" in out

    def test_run_valid_file(self, qapp, tmp_path):
        paw_file = tmp_path / "test.paw"
        paw_file.write_text('<Window title="Test"/>', encoding="utf-8")

        from pawui.runtime import Runtime
        rt = Runtime(paw_file.read_text(encoding="utf-8"), str(paw_file))
        rt.run(block=False)
        assert rt is not None
        rt.root.close()

    def test_run_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            run("nonexistent.paw")

    def test_check_valid_file(self, tmp_path, capsys):
        paw_file = tmp_path / "test.paw"
        paw_file.write_text('<Window title="Test"><Text>Hello</Text></Window>', encoding="utf-8")

        assert check(str(paw_file)) == 0
        out = capsys.readouterr().out
        assert "syntax OK" in out
        assert "Elements: 1" in out

    def test_check_invalid_file(self, tmp_path, capsys):
        paw_file = tmp_path / "bad.paw"
        paw_file.write_text('<Window><Text>Unclosed', encoding="utf-8")

        assert check(str(paw_file)) == 1
        out = capsys.readouterr().err
        assert "error" in out.lower()

    def test_check_nonexistent(self, capsys):
        assert check("nonexistent.paw") == 1
        out = capsys.readouterr().err
        assert "not found" in out

    def test_check_detects_components(self, tmp_path, capsys):
        paw_file = tmp_path / "test.paw"
        paw_file.write_text('''
        <Component name="Card"><Text/></Component>
        <Component name="Button"><Button/></Component>
        <Window/>
        ''', encoding="utf-8")

        assert check(str(paw_file)) == 0
        out = capsys.readouterr().out
        assert "Component: Card" in out
        assert "Component: Button" in out

    def test_schema_cmd(self, capsys):
        assert schema_cmd() == 0
        out = capsys.readouterr().out
        schema = json.loads(out)
        assert "components" in schema
        assert "Window" in schema["components"]
        assert "Button" in schema["components"]
        assert "animation_props" in schema
        assert "theme" in schema

    def test_render_valid_file(self, qapp, tmp_path, capsys):
        paw_file = tmp_path / "test.paw"
        paw_file.write_text('<Window title="Test" width="400" height="300"/>', encoding="utf-8")

        assert render(str(paw_file)) == 0
        out = capsys.readouterr().out
        assert "render OK" in out
        assert "Test" in out

    def test_render_invalid_file(self, tmp_path, capsys):
        paw_file = tmp_path / "bad.paw"
        paw_file.write_text('<Window><Text>Unclosed', encoding="utf-8")

        assert render(str(paw_file)) == 1
        out = capsys.readouterr().err
        assert "error" in out.lower()

    def test_render_nonexistent(self, capsys):
        assert render("nonexistent.paw") == 1
        out = capsys.readouterr().err
        assert "not found" in out

    def test_main_check_command(self, tmp_path):
        paw_file = tmp_path / "test.paw"
        paw_file.write_text('<Window/>', encoding="utf-8")
        assert main(["check", str(paw_file)]) == 0

    def test_main_schema_command(self):
        assert main(["schema"]) == 0

    def test_main_render_command(self, qapp, tmp_path):
        paw_file = tmp_path / "test.paw"
        paw_file.write_text('<Window/>', encoding="utf-8")
        assert main(["render", str(paw_file)]) == 0

    def test_main_check_missing_arg(self, capsys):
        assert main(["check"]) == 2
        out = capsys.readouterr().err
        assert "Usage" in out

    def test_main_render_missing_arg(self, capsys):
        assert main(["render"]) == 2
        out = capsys.readouterr().err
        assert "Usage" in out
