"""Tests for the workflow input model and Hubbard structure handling."""

from aiida import orm

from aiida_polaron_mbpt.workflows.polaron_mbpt import (
    PolaronMBPTWorkChain,
    make_hubbard_structure,
    to_plain_structure,
)


def make_structure():
    structure = orm.StructureData(
        cell=((3.0, 0.0, 0.0), (0.0, 3.0, 0.0), (0.0, 0.0, 3.0)),
        pbc=(True, True, True),
    )
    structure.append_atom(position=(0.0, 0.0, 0.0), symbols="Fe")
    structure.append_atom(position=(1.5, 1.5, 1.5), symbols="O")
    return structure


def test_make_hubbard_structure_and_strip_metadata():
    structure = make_structure()
    hubbard_structure = make_hubbard_structure(
        structure,
        orm.Dict(dict={"Fe": {"manifold": "3d", "value": 4.0}}),
    )

    assert hubbard_structure.hubbard.parameters[0].value == 4.0
    assert hubbard_structure.hubbard.parameters[0].atom_manifold == "3d"

    plain = to_plain_structure(hubbard_structure)
    assert type(plain) is orm.StructureData
    assert plain.get_kind_names() == structure.get_kind_names()


def test_relax_parameter_modes():
    parameters = {"CONTROL": {"calculation": "scf"}, "ELECTRONS": {"startingwfc": "atomic"}}

    from_scratch = PolaronMBPTWorkChain._set_relax_parameters(parameters, restart=False).get_dict()
    assert from_scratch["CONTROL"]["calculation"] == "relax"
    assert from_scratch["CONTROL"]["restart_mode"] == "from_scratch"
    assert "startingwfc" not in from_scratch["ELECTRONS"]

    from_wavefunctions = PolaronMBPTWorkChain._set_relax_parameters(parameters, restart=True).get_dict()
    assert from_wavefunctions["CONTROL"]["calculation"] == "relax"
    assert from_wavefunctions["CONTROL"]["restart_mode"] == "from_scratch"
    assert from_wavefunctions["ELECTRONS"]["startingwfc"] == "file"


def test_quality_checks():
    structure = make_structure()
    displaced = orm.StructureData(cell=structure.cell, pbc=structure.pbc)
    displaced.append_atom(position=(0.0, 0.0, 0.0), symbols="Fe")
    displaced.append_atom(position=(2.0, 1.5, 1.5), symbols="O")

    assert PolaronMBPTWorkChain._maximum_structure_displacement(structure, displaced) == 0.5


def test_workflow_spec_contains_all_stages():
    spec = PolaronMBPTWorkChain.spec()

    for namespace in ("relax_1", "relax_2", "relax_3", "yambo"):
        assert namespace in spec.inputs

    assert "stop_if_metal" in spec.inputs["yambo"]

    for output in ("relax_1_structure", "relax_2_structure", "relax_3_structure", "final_structure"):
        assert output in spec.outputs
