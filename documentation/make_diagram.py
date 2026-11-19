"""Membuat documentation/data-flow-diagram.png (opsional, butuh matplotlib).

    python documentation/make_diagram.py
"""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent / "data-flow-diagram.png"

STEPS = [
    ("Raw Dataset", "data/raw/\nautomobileEDA_dirty_training.csv\n205 baris x 30 kolom", "#E8EEF7", "#3B5B92"),
    ("Load Data", "load_data()\npd.read_csv()", "#E7F4EC", "#2E7D4F"),
    ("Data Inspection", "inspect_data()\nhead, shape, dtypes,\nmissing, duplikat, nilai unik", "#E7F4EC", "#2E7D4F"),
    ("Data Cleaning", "clean_data()\nstandarisasi kategori\nhapus duplikat, perbaiki tipe data\nisi / hapus missing values\ncek nilai tidak wajar", "#E7F4EC", "#2E7D4F"),
    ("Data Transformation", "transform_data()\nMin-Max Scaling (6 kolom)\nOne-Hot, Ordinal &\nFrequency Encoding", "#E7F4EC", "#2E7D4F"),
    ("Processed Dataset", "save_data()\ndata/processed/\nautomobileEDA_processed.csv\n198 baris x 57 kolom", "#FDF1E3", "#B5651D"),
]
PHASES = [("EXTRACT", 0, 1), ("TRANSFORM", 2, 4), ("LOAD", 5, 5)]

fig, ax = plt.subplots(figsize=(20.5, 5.4), dpi=150)
ax.set_xlim(0, 20.6)
ax.set_ylim(0, 5.2)
ax.axis("off")

box_w, box_h, gap, y = 3.0, 2.3, 0.45, 1.1
xs = [0.3 + i * (box_w + gap) for i in range(len(STEPS))]

for (title, detail, fill, edge), x in zip(STEPS, xs):
    ax.add_patch(FancyBboxPatch((x, y), box_w, box_h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                facecolor=fill, edgecolor=edge, linewidth=2))
    ax.text(x + box_w / 2, y + box_h - 0.38, title, ha="center", va="center",
            fontsize=12.5, fontweight="bold", color=edge)
    ax.text(x + box_w / 2, y + box_h / 2 - 0.25, detail, ha="center", va="center",
            fontsize=8.6, color="#333333", linespacing=1.45)

for x0, x1 in zip(xs[:-1], xs[1:]):
    ax.add_patch(FancyArrowPatch((x0 + box_w + 0.04, y + box_h / 2), (x1 - 0.04, y + box_h / 2),
                                 arrowstyle="-|>", mutation_scale=18, linewidth=2, color="#555555"))

for label, i0, i1 in PHASES:
    x0, x1 = xs[i0], xs[i1] + box_w
    ax.plot([x0, x1], [y + box_h + 0.35] * 2, color="#888888", linewidth=1.5)
    ax.text((x0 + x1) / 2, y + box_h + 0.6, label, ha="center", va="center",
            fontsize=11, fontweight="bold", color="#555555")

ax.text(10.3, 4.85, "Data Flow Diagram - Automobile Data Pipeline (src/pipeline.py)",
        ha="center", va="center", fontsize=15, fontweight="bold", color="#222222")
ax.text(10.3, 0.55, "Dataset mentah hanya dibaca (read-only) - hasil disimpan sebagai file baru; "
        "integritas raw diverifikasi dengan hash MD5", ha="center", va="center",
        fontsize=9.5, style="italic", color="#666666")

fig.savefig(OUT, bbox_inches="tight", facecolor="white")
print(f"Diagram tersimpan: {OUT}")
