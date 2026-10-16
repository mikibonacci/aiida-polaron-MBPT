"""DFT+U relaxation and Yambo GW/QP/BSE workflow."""

from __future__ import annotations

from copy import deepcopy
from numbers import Real
from typing import Any, Iterable

from aiida import orm
from aiida.common import AttributeDict
from aiida.engine import ToContext, WorkChain

from aiida_quantumespresso.common.hubbard import Hubbard
from aiida_quantumespresso.data.hubbard_structure import HubbardStructureData
from aiida_quantumespresso.workflows.pw.base import PwBaseWorkChain


def _get_yambo_workflow():
    """Import Yambo lazily because the current local plugin loads an AiiDA profile at import time."""

    from aiida_yambo.workflows.yambowf import YamboWorkflow

    return YamboWorkflow


def _normalise_hubbard_entries(configuration: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert the supported U mapping formats to a common representation.

    The preferred input format is::

        {"Fe": {"manifold": "3d", "value": 4.0}}

    A compact ``{"Fe-3d": 4.0}`` form is also accepted.  Values are in eV.
    """

    if "parameters" in configuration:
        raw_entries: Iterable[Any] = configuration["parameters"]
    else:
        raw_entries = (
            {"kind": key, **value} if isinstance(value, dict) else {"kind": key, "value": value}
            for key, value in configuration.items()
        )

    entries = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError("Hubbard parameters must be dictionaries.")

        kind = raw_entry.get("kind")
        manifold = raw_entry.get("manifold", raw_entry.get("orbital"))
        value = raw_entry.get("value", raw_entry.get("u", raw_entry.get("U")))
        hubbard_type = raw_entry.get("hubbard_type", "Ueff")

        if manifold is None and isinstance(kind, str) and "-" in kind:
            kind, manifold = kind.rsplit("-", maxsplit=1)

        if not kind or not manifold or value is None:
            raise ValueError(
                "Each Hubbard parameter must define `kind`, `manifold`, and `value`, "
                "for example `{'Fe': {'manifold': '3d', 'value': 4.0}}`."
            )
        if not isinstance(value, Real):
            raise ValueError(f"Hubbard value for `{kind}` must be a number.")

        entries.append(
            {
                "kind": str(kind),
                "manifold": str(manifold),
                "value": float(value),
                "hubbard_type": str(hubbard_type),
            }
        )

    if not entries:
        raise ValueError("At least one Hubbard parameter is required.")
    return entries


def make_hubbard_structure(
    structure: orm.StructureData,
    configuration: orm.Dict,
    projectors: str = "atomic",
    formulation: str = "dudarev",
) -> HubbardStructureData:
    """Create a Hubbard-aware copy of a structure from a ``Dict`` configuration."""

    hubbard_structure = HubbardStructureData.from_structure(structure)
    kind_names = set(structure.get_kind_names())

    for entry in _normalise_hubbard_entries(configuration.get_dict()):
        if entry["kind"] not in kind_names:
            raise ValueError(
                f"Hubbard parameter refers to kind `{entry['kind']}`, but the structure contains "
                f"{sorted(kind_names)}."
            )
        hubbard_structure.initialize_onsites_hubbard(
            entry["kind"],
            entry["manifold"],
            entry["value"],
            hubbard_type=entry["hubbard_type"],
            use_kinds=True,
        )

    hubbard = Hubbard.from_list(
        hubbard_structure.hubbard.to_list(),
        projectors=projectors,
        formulation=formulation,
    )
    hubbard_structure.hubbard = hubbard
    return hubbard_structure


def to_plain_structure(structure: orm.StructureData) -> orm.StructureData:
    """Return a plain ``StructureData`` copy without Hubbard metadata."""

    if not isinstance(structure, HubbardStructureData):
        return structure

    plain_structure = orm.StructureData(cell=structure.cell, pbc=structure.pbc)
    for kind in structure.kinds:
        plain_structure.append_kind(orm.Kind(symbols=kind.symbol, name=kind.name))
    for site in structure.sites:
        plain_structure.append_site(orm.Site(kind_name=site.kind_name, position=site.position))
    return plain_structure


class PolaronMBPTWorkChain(WorkChain):
    """Run two DFT+U relaxations, a k-point-refined relaxation, and Yambo BSE@GW."""

    @classmethod
    def define(cls, spec):
        """Define inputs, outputs, and the sequential workflow outline."""

        super().define(spec)
        yambo_workflow = _get_yambo_workflow()

        spec.input("structure", valid_type=orm.StructureData, help="Initial structure.")
        spec.input("pw_code", valid_type=orm.AbstractCode, help="Quantum ESPRESSO `pw.x` code.")
        spec.input(
            "pseudo_family",
            valid_type=orm.Str,
            help="Label of the AiiDA pseudo family used for all QE calculations.",
        )
        spec.input("yambo_code", valid_type=orm.AbstractCode, help="Yambo main code.")
        spec.input("yambo_preprocessing_code", valid_type=orm.AbstractCode, help="Yambo preprocessing code.")

        spec.input("hubbard_u_initial", valid_type=orm.Dict, help="Hubbard U values for the first relaxation.")
        spec.input("hubbard_u_final", valid_type=orm.Dict, help="Hubbard U values for relaxations two and three.")
        spec.input(
            "hubbard_projectors",
            valid_type=orm.Str,
            default=lambda: orm.Str("atomic"),
            help="Projector type for the QE HUBBARD card.",
        )
        spec.input(
            "hubbard_formulation",
            valid_type=orm.Str,
            default=lambda: orm.Str("dudarev"),
            help="Hubbard formulation for the QE HUBBARD card.",
        )

        spec.input("kpoints_gamma", valid_type=orm.KpointsData, help="Gamma-only mesh for the first two relaxations.")
        spec.input("kpoints_relax3", valid_type=orm.KpointsData, help="Mesh for the third relaxation.")
        spec.input(
            "kpoints_yambo",
            valid_type=orm.KpointsData,
            required=False,
            help="Mesh for Yambo SCF/NSCF; defaults to `kpoints_relax3`.",
        )

        relax_exclude = ("pw.structure", "pw.parent_folder", "pw.code", "pw.pseudos", "kpoints")
        for namespace in ("relax_1", "relax_2", "relax_3"):
            spec.expose_inputs(
                PwBaseWorkChain,
                namespace=namespace,
                exclude=relax_exclude,
                namespace_options={
                    "required": True,
                    "populate_defaults": False,
                    "help": f"Inputs for QE relaxation stage {namespace[-1]}.",
                },
            )

        yambo_exclude = (
            "scf.pw.structure",
            "nscf.pw.structure",
            "scf.pw.code",
            "nscf.pw.code",
            "scf.pw.pseudos",
            "nscf.pw.pseudos",
            "scf.kpoints",
            "nscf.kpoints",
            "parent_folder",
            "qp.yambo.code",
            "bse.yambo.code",
            "qp.yambo.preprocessing_code",
            "bse.yambo.preprocessing_code",
        )
        spec.expose_inputs(
            yambo_workflow,
            namespace="yambo",
            exclude=yambo_exclude,
            namespace_options={
                "required": True,
                "populate_defaults": False,
                "help": "Inputs for the DFT SCF/NSCF and Yambo GW/QP/BSE workflow.",
            },
        )

        spec.outline(
            cls.run_relax_1,
            cls.inspect_relax_1,
            cls.run_relax_2,
            cls.inspect_relax_2,
            cls.run_relax_3,
            cls.inspect_relax_3,
            cls.run_yambo,
            cls.inspect_yambo,
            cls.results,
        )

        for namespace in ("relax_1", "relax_2", "relax_3"):
            spec.expose_outputs(PwBaseWorkChain, namespace=namespace)
        spec.expose_outputs(yambo_workflow, namespace="yambo")

        spec.output("relax_1_structure", valid_type=orm.StructureData, required=False)
        spec.output("relax_2_structure", valid_type=orm.StructureData, required=False)
        spec.output("relax_3_structure", valid_type=orm.StructureData, required=False)
        spec.output("final_structure", valid_type=orm.StructureData, required=False)

        spec.exit_code(401, "ERROR_RELAX_1_FAILED", message="The first QE relaxation failed.")
        spec.exit_code(402, "ERROR_RELAX_2_FAILED", message="The second QE relaxation failed.")
        spec.exit_code(403, "ERROR_RELAX_3_FAILED", message="The third QE relaxation failed.")
        spec.exit_code(404, "ERROR_YAMBO_FAILED", message="The YamboWorkflow failed.")
        spec.exit_code(
            405,
            "ERROR_MISSING_OUTPUT_STRUCTURE",
            message="A QE relaxation did not return an output structure.",
        )

    @staticmethod
    def _set_relax_parameters(parameters: dict[str, Any], restart: bool) -> orm.Dict:
        """Normalize parameters for an ionic-only relaxation."""

        parameters = deepcopy(parameters)
        parameters.setdefault("CONTROL", {})
        parameters.setdefault("ELECTRONS", {})
        parameters["CONTROL"]["calculation"] = "relax"
        parameters["CONTROL"]["wf_collect"] = True
        parameters.pop("CELL", None)

        if restart:
            parameters["CONTROL"]["restart_mode"] = "from_scratch"
            parameters["ELECTRONS"]["startingwfc"] = "file"
            parameters["ELECTRONS"].pop("startingpot", None)
        else:
            parameters["CONTROL"]["restart_mode"] = "from_scratch"
            parameters["ELECTRONS"].pop("startingwfc", None)
            parameters["ELECTRONS"].pop("startingpot", None)

        return orm.Dict(dict=parameters)

    def _pseudos(self, structure: orm.StructureData) -> dict[str, orm.Data]:
        """Load the configured pseudo family and return pseudos for ``structure``."""

        family = orm.load_group(self.inputs.pseudo_family.value)
        return family.get_pseudos(structure=structure)

    def _relax_inputs(
        self,
        namespace: str,
        structure: orm.StructureData,
        kpoints: orm.KpointsData,
        restart: bool = False,
        parent_folder: orm.RemoteData | None = None,
    ) -> AttributeDict:
        """Build one child ``PwBaseWorkChain`` input dictionary."""

        inputs = self.exposed_inputs(PwBaseWorkChain, namespace=namespace)
        inputs.pw.structure = structure
        inputs.pw.code = self.inputs.pw_code
        inputs.pw.pseudos = self._pseudos(structure)
        inputs.kpoints = kpoints
        inputs.pw.parameters = self._set_relax_parameters(inputs.pw.parameters.get_dict(), restart=restart)
        # The first stage must keep its remote folder available for stage two's wavefunction restart.
        inputs.clean_workdir = orm.Bool(False)
        inputs.metadata.call_link_label = namespace

        if parent_folder is not None:
            inputs.pw.parent_folder = parent_folder
        return inputs

    @staticmethod
    def _output_structure(node: orm.ProcessNode) -> orm.StructureData | None:
        """Return a child output structure, if present."""

        return node.outputs.output_structure if "output_structure" in node.outputs else None

    def run_relax_1(self):
        """Submit the first Gamma-only DFT+U relaxation."""

        structure = make_hubbard_structure(
            self.inputs.structure,
            self.inputs.hubbard_u_initial,
            projectors=self.inputs.hubbard_projectors.value,
            formulation=self.inputs.hubbard_formulation.value,
        )
        running = self.submit(
            PwBaseWorkChain,
            **self._relax_inputs("relax_1", structure, self.inputs.kpoints_gamma),
        )
        self.report(f"submitted first DFT+U relaxation PwBaseWorkChain<{running.pk}>")
        return ToContext(relax_1=running)

    def inspect_relax_1(self):
        """Check the first relaxation and its structure output."""

        node = self.ctx.relax_1
        if not node.is_finished_ok:
            self.report(f"first QE relaxation failed with exit status {node.exit_status}")
            return self.exit_codes.ERROR_RELAX_1_FAILED
        if self._output_structure(node) is None:
            return self.exit_codes.ERROR_MISSING_OUTPUT_STRUCTURE

    def run_relax_2(self):
        """Restart from the first relaxation's stored wavefunctions with new U values."""

        parent_structure = self._output_structure(self.ctx.relax_1)
        structure = make_hubbard_structure(
            parent_structure,
            self.inputs.hubbard_u_final,
            projectors=self.inputs.hubbard_projectors.value,
            formulation=self.inputs.hubbard_formulation.value,
        )
        running = self.submit(
            PwBaseWorkChain,
            **self._relax_inputs(
                "relax_2",
                structure,
                self.inputs.kpoints_gamma,
                restart=True,
                parent_folder=self.ctx.relax_1.outputs.remote_folder,
            ),
        )
        self.report(f"submitted wavefunction-restart DFT+U relaxation PwBaseWorkChain<{running.pk}>")
        return ToContext(relax_2=running)

    def inspect_relax_2(self):
        """Check the second relaxation and its structure output."""

        node = self.ctx.relax_2
        if not node.is_finished_ok:
            self.report(f"second QE relaxation failed with exit status {node.exit_status}")
            return self.exit_codes.ERROR_RELAX_2_FAILED
        if self._output_structure(node) is None:
            return self.exit_codes.ERROR_MISSING_OUTPUT_STRUCTURE

    def run_relax_3(self):
        """Run the final DFT+U relaxation with the refined k-point mesh."""

        structure = make_hubbard_structure(
            self._output_structure(self.ctx.relax_2),
            self.inputs.hubbard_u_final,
            projectors=self.inputs.hubbard_projectors.value,
            formulation=self.inputs.hubbard_formulation.value,
        )
        running = self.submit(
            PwBaseWorkChain,
            **self._relax_inputs("relax_3", structure, self.inputs.kpoints_relax3),
        )
        self.report(f"submitted k-point-refined DFT+U relaxation PwBaseWorkChain<{running.pk}>")
        return ToContext(relax_3=running)

    def inspect_relax_3(self):
        """Check the final QE relaxation and its structure output."""

        node = self.ctx.relax_3
        if not node.is_finished_ok:
            self.report(f"third QE relaxation failed with exit status {node.exit_status}")
            return self.exit_codes.ERROR_RELAX_3_FAILED
        if self._output_structure(node) is None:
            return self.exit_codes.ERROR_MISSING_OUTPUT_STRUCTURE

    def run_yambo(self):
        """Submit the DFT-only SCF/NSCF/GW/QP/BSE workflow."""

        yambo_workflow = _get_yambo_workflow()
        structure = to_plain_structure(self._output_structure(self.ctx.relax_3))
        inputs = self.exposed_inputs(yambo_workflow, namespace="yambo")
        inputs.scf.pw.structure = structure
        inputs.nscf.pw.structure = structure
        inputs.scf.pw.code = self.inputs.pw_code
        inputs.nscf.pw.code = self.inputs.pw_code
        inputs.scf.pw.pseudos = self._pseudos(structure)
        inputs.nscf.pw.pseudos = self._pseudos(structure)

        kpoints = self.inputs.kpoints_yambo if "kpoints_yambo" in self.inputs else self.inputs.kpoints_relax3
        inputs.scf.kpoints = kpoints
        inputs.nscf.kpoints = kpoints

        for namespace, calculation in (("scf", "scf"), ("nscf", "nscf")):
            parameters = inputs[namespace].pw.parameters.get_dict()
            parameters = deepcopy(parameters)
            parameters.setdefault("CONTROL", {})["calculation"] = calculation
            parameters["CONTROL"]["wf_collect"] = True
            inputs[namespace].pw.parameters = orm.Dict(dict=parameters)

        for namespace in ("qp", "bse"):
            inputs[namespace].yambo.code = self.inputs.yambo_code
            inputs[namespace].yambo.preprocessing_code = self.inputs.yambo_preprocessing_code

        inputs.metadata.call_link_label = "yambo"
        running = self.submit(yambo_workflow, **inputs)
        self.report(f"submitted DFT/YamboWorkflow<{running.pk}>")
        return ToContext(yambo=running)

    def inspect_yambo(self):
        """Check the final Yambo workflow."""

        if not self.ctx.yambo.is_finished_ok:
            self.report(f"YamboWorkflow failed with exit status {self.ctx.yambo.exit_status}")
            return self.exit_codes.ERROR_YAMBO_FAILED

    def results(self):
        """Expose child outputs and convenient structure aliases."""

        yambo_workflow = _get_yambo_workflow()
        relax_1_structure = self._output_structure(self.ctx.relax_1)
        relax_2_structure = self._output_structure(self.ctx.relax_2)
        relax_3_structure = self._output_structure(self.ctx.relax_3)

        self.out("relax_1_structure", relax_1_structure)
        self.out("relax_2_structure", relax_2_structure)
        self.out("relax_3_structure", relax_3_structure)
        self.out("final_structure", relax_3_structure)

        for namespace, node in (
            ("relax_1", self.ctx.relax_1),
            ("relax_2", self.ctx.relax_2),
            ("relax_3", self.ctx.relax_3),
        ):
            self.out_many(self.exposed_outputs(node, PwBaseWorkChain, namespace=namespace))
        self.out_many(self.exposed_outputs(self.ctx.yambo, yambo_workflow, namespace="yambo"))
