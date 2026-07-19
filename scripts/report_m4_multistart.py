"""Write a human-readable, non-selective M4 basin-dispersion report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TARGET = {"validation_rmse": 4.682382, "validation_bic": 4578.578337, "test_rmse": 0.857599}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()
    directory = root / "runs" / "m4" / "multistart"
    merged = json.loads((directory / "all_starts.json").read_text(encoding="utf-8"))
    verdict = json.loads((root / "runs" / "m4" / "verdict.json").read_text(encoding="utf-8"))
    selected = sorted(merged["selected"], key=lambda row: float(row["validation_bic"]))
    std4 = [row for row in merged["outcomes"] if row["model"] == "STD_4R3C_two_masses_plus_air_shunt"]
    valid_std4 = [row for row in std4 if row.get("validation_rmse") is not None]
    nearest = min(valid_std4, key=lambda row: abs(float(row["validation_rmse"]) - TARGET["validation_rmse"]))
    lines = [
        "# M4 — rapport de dispersion multi-start",
        "",
        f"Verdict : **{verdict['validation_route']}** — {verdict['conclusion']}.",
        "",
        "Les redémarrages sont retenus exclusivement par MSE train. Les valeurs validation/test ci-dessous sont rapportées après coup ; elles n’ont servi à choisir aucun redémarrage.",
        "",
        "## Classement des structures retenues",
        "",
        "| Rang BIC validation | Structure | Départ retenu | MSE train | RMSE validation | BIC validation | RMSE test | statut |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for rank, row in enumerate(selected, start=1):
        lines.append(
            f"| {rank} | {row['model']} | {row['selected_start_id']} | {float(row['train_mse']):.9g} | {float(row['validation_rmse']):.6f} | {float(row['validation_bic']):.6f} | {float(row['test_rmse']):.6f} | success={row['fit_success']} |"
        )
    lines += [
        "",
        "## 4R3C et cible article/notebook",
        "",
        f"Cible oracle indépendante : RMSE validation {TARGET['validation_rmse']:.6f} °C ; BIC {TARGET['validation_bic']:.6f} ; RMSE test {TARGET['test_rmse']:.6f} °C.",
        f"Départ 4R3C le plus proche en RMSE validation (non retenu par ce critère) : start {nearest['start_id']}, RMSE {float(nearest['validation_rmse']):.6f}, BIC {float(nearest['validation_bic']):.6f}, test {float(nearest['test_rmse']):.6f}, MSE train {float(nearest['train_mse']):.9g}.",
        "",
        "Ce rapprochement est descriptif seulement. Même s’il était proche de la cible, il ne peut pas remplacer le départ retenu sans violer la règle de sélection train.",
        "",
        "## Interprétation de la dispersion",
        "",
        "Les q05–q95 et fractions de départs proches du meilleur sont des plages empiriques de la banque fixée. Elles ne sont pas des intervalles de confiance statistiques ni une cartographie exhaustive des bassins.",
    ]
    path = directory / "m4_multistart_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
