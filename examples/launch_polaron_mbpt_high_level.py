#!/usr/bin/env runaiida
"""Submit the Silicon polaron workflow using aiida-yambo's high-level API.

The polaron-specific DFT+U relaxations still use the exposed Quantum ESPRESSO
inputs.  The DFT-only SCF/NSCF and GW/QP/BSE part is configured through
``YamboWorkflow.get_builder_from_protocol`` and ``YamboInputManager``.
"""

from aiida import load_profile, orm
from aiida.engine import submit
from aiida_quantumespresso.common.types import ElectronicType, SpinType

from aiida_polaron_mbpt.workflows.polaron_mbpt import PolaronMBPTWorkChain
from aiida_yambo.utils.high_level_API.yambo_model import YamboInputManager
from aiida_yambo.workflows.yambowf import YamboWorkflow


def make_structure():
    """Return a two-atom primitive diamond-silicon structure."""

    lattice_constant = 5.43
    structure = orm.StructureData(
        cell=(
            (0.0, lattice_constant / 2.0, lattice_constant / 2.0),
            (lattice_constant / 2.0, 0.0, lattice_constant / 2.0),
            (lattice_constant / 2.0, lattice_constant / 2.0, 0.0),
        ),
        pbc=(True, True, True),
    )
    structure.append_atom(position=(0.0, 0.0, 0.0), symbols="Si", name="Si1")
    structure.append_atom(
        position=(lattice_constant / 4.0, lattice_constant / 4.0, lattice_constant / 4.0),
        symbols="Si",
        name="Si2",
    )
    return structure


def make_relax_parameters():
    """Return common QE ionic-relaxation parameters."""

    return orm.Dict(
        dict={
            "CONTROL": {
                "calculation": "relax",
                "tstress": True,
                "tprnfor": True,
                "etot_conv_thr": 1.0e-5,
            },
            "SYSTEM": {
                "ecutwfc": 80.0,
                "ecutrho": 640.0,
                "occupations": "fixed",
            },
            "ELECTRONS": {
                "conv_thr": 1.0e-8,
                "electron_maxstep": 200,
            },
            "IONS": {
                "ion_dynamics": "bfgs",
            },
        }
    )


def _copy_yambo_leaf(target, source, keys):
    """Copy only inputs accepted by the corresponding exposed namespace."""

    for key in keys:
        if key in source:
            target[key] = source[key]


def configure_yambo_from_protocol(
    builder,
    structure,
    pw_code,
    yambo_code,
    preprocessing_code,
    pseudo_family,
):
    """Configure ``builder.yambo`` from the aiida-yambo high-level API.

    The outer polaron workchain deliberately excludes structures, codes,
    pseudos, and k-points from its Yambo namespace because it supplies those
    at runtime from the relaxed structure.  Therefore, only the protocol and
    physics/resource inputs are copied from the high-level builder.
    """

    protocol_builder = YamboWorkflow.get_builder_from_protocol(
        pw_code=pw_code,
        preprocessing_code=preprocessing_code,
        code=yambo_code,
        structure=structure,
        pseudo_family=pseudo_family,
        protocol_qe="moderate",
        protocol="moderate",
        calc_type="bse@qp",
        electronic_type=ElectronicType.INSULATOR,
        spin_type=SpinType.NONE,
    )
    manager = YamboInputManager(
        **YamboInputManager.get_nested_inputs(
            protocol_builder,
            what="YamboWorkflow",
            mode="builder",
        )
    )

    # DFT settings.  The outer workflow replaces the k-points with its
    # kpoints_yambo input, but setting them here keeps the manager complete.
    manager.scf.set_kmesh([2, 2, 2])
    manager.nscf.set_kmesh([2, 2, 2])
    manager.scf.set_pw_parameter("SYSTEM", "ecutwfc", 80.0)
    manager.nscf.set_pw_parameter("SYSTEM", "ecutwfc", 80.0)
    manager.scf.set_pw_parameter("SYSTEM", "ecutrho", 640.0)
    manager.nscf.set_pw_parameter("SYSTEM", "ecutrho", 640.0)
    manager.set_nscf_nbnd(32)
    manager.scf.set_resources(mpi=4, time=24 * 60 * 60)
    manager.nscf.set_resources(mpi=4, time=24 * 60 * 60)

    # GW/QP settings.
    manager.qp.set_arguments(["dipoles", "HF_and_locXC", "gw0", "ppa"])
    manager.qp.set_variable("Chimod", "hartree")
    manager.qp.set_variable("DysSolver", "n")
    manager.qp.set_variable("GTermKind", "BG")
    manager.qp.set_Nb(value=16, add_if_not_present=True)
    manager.qp.set_Gcut(value=2, add_if_not_present=True)
    manager.qp.set_resources(mpi=4, time=24 * 60 * 60)
    manager.qp.settings.update({"INITIALISE": False, "COPY_DBS": False})

    # BSE@GW settings.
    manager.bse.set_arguments(["em1s", "bse", "bss", "optics", "dipoles"])
    manager.bse.set_variable("BSEmod", "resonant")
    manager.bse.set_variable("BSKmod", "SEX")
    manager.bse.set_variable("BSSmod", "d")
    manager.bse.set_variable("Lkind", "full")
    manager.bse.set_variable("Chimod", "hartree")
    manager.bse.set_variable("DysSolver", "n")
    manager.bse.set_variable("BSEQptR", [[1, 1], ""])
    manager.bse.set_BSENb(value=16, add_if_not_present=True)
    manager.bse.set_BSEGcut(value=2, add_if_not_present=True)
    manager.bse.set_BSEbands([3, 6])
    manager.bse.set_variable("BEnSteps", [100, ""])
    manager.bse.set_variable("BEnRange", [[0.0, 10.0], "eV"])
    manager.bse.set_variable("BS_CPU", "2 2 1")
    manager.bse.set_variable("BS_ROLEs", "k eh t")
    manager.bse.set_resources(mpi=4, time=24 * 60 * 60)
    manager.bse.settings.update({"INITIALISE": False, "COPY_DBS": False})

    manager.set_QP_subsets_dict(
        range_QP=5.0,
        range_spectrum=10.0,
        qp_per_subset=16,
        parallel_runs=1,
    )
    manager.additional_parsing = ["gap_", "lowest_exciton"]

    yambo_inputs = manager.generate_AiiDA_inputs(what="YamboWorkflow")

    # The outer workflow owns these data-node inputs and supplies them from
    # the stage-3 structure, so copy only the configurable leaves.
    for namespace in ("scf", "nscf"):
        _copy_yambo_leaf(
            builder.yambo[namespace].pw,
            yambo_inputs[namespace]["pw"],
            ("parameters", "settings", "parallelization", "metadata"),
        )
    for namespace in ("qp", "bse"):
        _copy_yambo_leaf(
            builder.yambo[namespace].yambo,
            yambo_inputs[namespace]["yambo"],
            ("parameters", "settings", "metadata"),
        )

    for key in ("QP_subsets_dict", "additional_parsing"):
        if key in yambo_inputs:
            builder.yambo[key] = yambo_inputs[key]

    builder.yambo.stop_if_metal = True
    return builder


def main():
    load_profile()

    structure = make_structure()
    pw_code = orm.load_code("qe-7.5-gcc-spack@corvina-direct")
    yambo_code = orm.load_code("yambo-5.3.0-gcc@corvina-direct")
    preprocessing_code = orm.load_code("p2y-5.3.0-gcc@corvina-direct")
    pseudo_family = "SSSP/1.3/PBE/efficiency"

    gamma = orm.KpointsData()
    gamma.set_kpoints_mesh((1, 1, 1))

    final_mesh = orm.KpointsData()
    final_mesh.set_kpoints_mesh((2, 2, 2))

    builder = PolaronMBPTWorkChain.get_builder()
    builder.structure = structure
    builder.pw_code = pw_code
    builder.pseudo_family = orm.Str(pseudo_family)
    builder.yambo_code = yambo_code
    builder.yambo_preprocessing_code = preprocessing_code
    builder.kpoints_gamma = gamma
    builder.kpoints_relax3 = final_mesh
    builder.kpoints_yambo = final_mesh
    builder.max_force_threshold = orm.Float(0.2)
    builder.max_structure_displacement = orm.Float(0.5)

    # Example values only: choose the Hubbard manifold and U values for the
    # pseudopotential and physical system used in the actual calculation.
    builder.hubbard_u_initial = orm.Dict(
        dict={
            "Si1": {"manifold": "3p", "value": 2.0},
            "Si2": {"manifold": "3p", "value": 10.0},
        }
    )
    builder.hubbard_u_final = orm.Dict(
        dict={
            "Si1": {"manifold": "3p", "value": 2.0},
            "Si2": {"manifold": "3p", "value": 2.0},
        }
    )

    for namespace in ("relax_1", "relax_2", "relax_3"):
        builder[namespace].pw.parameters = make_relax_parameters()
        builder[namespace].pw.metadata.options = {
            "resources": {"num_machines": 1, "num_mpiprocs_per_machine": 4},
            "max_wallclock_seconds": 24 * 60 * 60,
        }

    configure_yambo_from_protocol(
        builder,
        structure,
        pw_code,
        yambo_code,
        preprocessing_code,
        pseudo_family,
    )

    node = submit(builder)
    print(f"Submitted PolaronMBPTWorkChain<{node.pk}>")


if __name__ == "__main__":
    main()
