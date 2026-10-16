#!/usr/bin/env runaiida
"""Example submission script for ``PolaronMBPTWorkChain``.

Edit the code labels, pseudo-family label, structure, numerical parameters, and
Yambo convergence settings before submitting on a real profile.
"""

from aiida import load_profile, orm
from aiida.engine import submit

from aiida_polaron_mbpt.workflows.polaron_mbpt import PolaronMBPTWorkChain


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
        name="Si2"
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

    # The top-level workflow exposes the current YamboWorkflow inputs. The
    # workflow itself supplies the QE codes, pseudos, structures, and k-points.
    builder.yambo.scf.pw.parameters = orm.Dict(
        dict={
            "CONTROL": {"calculation": "scf", "wf_collect": True},
            "SYSTEM": {"ecutwfc": 80.0, "ecutrho": 640.0, "nbnd": 16},
            "ELECTRONS": {"conv_thr": 1.0e-8},
        }
    )
    builder.yambo.nscf.pw.parameters = orm.Dict(
        dict={
            "CONTROL": {"calculation": "nscf", "wf_collect": True},
            "SYSTEM": {"ecutwfc": 80.0, "ecutrho": 640.0, "nbnd": 32},
            "ELECTRONS": {"conv_thr": 1.0e-8},
        }
    )
    builder.yambo.scf.pw.metadata.options = {
        "resources": {"num_machines": 1, "num_mpiprocs_per_machine": 4},
        "max_wallclock_seconds": 24 * 60 * 60,
    }
    builder.yambo.nscf.pw.metadata.options = builder.yambo.scf.pw.metadata.options

    builder.yambo.qp.yambo.parameters = orm.Dict(
        dict={
            "arguments": ["dipoles", "HF_and_locXC", "gw0", "ppa"],
            "variables": {
                "Chimod": "hartree",
                "DysSolver": "n",
                "GTermKind": "BG",
                "NGsBlkXp": [2, "Ry"],
                "BndsRnXp": [[1, 16], ""],
                "GbndRnge": [[1, 16], ""],
                "QPkrange": [[[1, 1, 1, 16]], ""],
            },
        }
    )
    builder.yambo.bse.yambo.parameters = orm.Dict(
        dict={
            "arguments": ["em1s", "bse", "bss", "optics", "dipoles"],
            "variables": {
                "BSEmod": "resonant",
                "BSKmod": "SEX",
                "BSSmod": "d",
                "Lkind": "full",
                "NGsBlkXs": [2, "Ry"],
                "BSENGBlk": [2, "Ry"],
                "Chimod": "hartree",
                "DysSolver": "n",
                "BSEQptR": [[1, 1], ""],
                "BSEBands": [[1, 16], ""],
                "BEnSteps": [100, ""],
                "BEnRange": [[0.0, 10.0], "eV"],
            },
        }
    )
    builder.yambo.qp.yambo.metadata.options = {
        "resources": {"num_machines": 1, "num_mpiprocs_per_machine": 4},
        "max_wallclock_seconds": 24 * 60 * 60,
    }
    builder.yambo.bse.yambo.metadata.options = builder.yambo.qp.yambo.metadata.options
    builder.yambo.qp.yambo.settings = orm.Dict(dict={"INITIALISE": False, "COPY_DBS": False})
    builder.yambo.bse.yambo.settings = orm.Dict(dict={"INITIALISE": False, "COPY_DBS": False})
    builder.yambo.QP_subsets_dict = orm.Dict(
        dict={"range_QP": 5.0, "range_spectrum": 10.0, "qp_per_subset": 16, "parallel_runs": 1}
    )

    node = submit(builder)
    print(f"Submitted PolaronMBPTWorkChain<{node.pk}>")


if __name__ == "__main__":
    main()
