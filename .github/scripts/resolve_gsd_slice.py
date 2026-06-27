import os
import re
from pathlib import Path

GSD_ROOT = Path(".gsd")
MILESTONES_ROOT = GSD_ROOT / "milestones"
STATE_FILE = GSD_ROOT / "STATE.md"
SLICE_LINE_RE = re.compile(
    r"^\s*-\s*\[(?P<mark>[ xX])\]\s*\*\*(?P<slice>S\d+):\s*(?P<title>[^*]+?)\*\*",
    re.MULTILINE,
)

def read_text(path):
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")

def output_value(value):
    return str(value).replace("%", "%25").replace("\n", "%0A").replace("\r", "%0D")

def write_outputs(**values):
    if "GITHUB_OUTPUT" not in os.environ:
        return
    output_path = os.environ["GITHUB_OUTPUT"]
    with open(output_path, "a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}={output_value(value)}\n")

def parse_state():
    state = read_text(STATE_FILE)
    milestone_match = re.search(
        r"^\*\*Active Milestone:\*\*\s*(?P<milestone>M[^\s:]+)", state, re.MULTILINE
    )
    slice_match = re.search(
        r"^\*\*Active Slice:\*\*\s*(?P<slice>S\d+)(?::\s*(?P<title>.+))?",
        state,
        re.MULTILINE,
    )
    completed = set(
        re.findall(r"^\s*-\s*\u2705\s*\*\*(?P<milestone>M[^:*]+):", state, re.MULTILINE)
    )
    return {
        "milestone": milestone_match.group("milestone") if milestone_match else "",
        "slice": slice_match.group("slice") if slice_match else "",
        "title": (slice_match.group("title") or "").strip() if slice_match else "",
        "completed_milestones": completed,
    }

def roadmap_files():
    if not MILESTONES_ROOT.exists():
        return []
    return sorted(MILESTONES_ROOT.glob("*/*-ROADMAP.md"))

def parse_roadmap(path):
    slices = []
    for match in SLICE_LINE_RE.finditer(read_text(path)):
        slices.append(
            {
                "milestone": path.parent.name,
                "slice": match.group("slice"),
                "title": match.group("title").strip(),
                "complete": match.group("mark").strip().lower() == "x",
                "roadmap": str(path),
            }
        )
    return slices

def find_roadmap_slice(milestone_id, slice_id):
    for path in roadmap_files():
        if path.parent.name != milestone_id:
            continue
        for item in parse_roadmap(path):
            if item["slice"] == slice_id:
                return item
    return None

def slice_dir(milestone_id, slice_id):
    return MILESTONES_ROOT / milestone_id / "slices" / slice_id

def slice_ready_for_implementation(milestone_id, slice_id, completed_milestones):
    if milestone_id in completed_milestones:
        return False

    roadmap_item = find_roadmap_slice(milestone_id, slice_id)
    if roadmap_item is not None and roadmap_item["complete"]:
        return False

    directory = slice_dir(milestone_id, slice_id)
    summary_file = directory / f"{slice_id}-SUMMARY.md"

    if summary_file.exists():
        return False
    
    if not list(directory.glob("*CONTEXT*.md")):
        return False
    
    return True

def select_implementation_slice():
    state = parse_state()
    completed_milestones = state["completed_milestones"]

    active_milestone = state["milestone"]
    active_slice = state["slice"]
    if active_milestone and active_slice and slice_ready_for_implementation(
        active_milestone, active_slice, completed_milestones
    ):
        roadmap_item = find_roadmap_slice(active_milestone, active_slice) or {}
        return {
            "milestone_id": active_milestone,
            "slice_id": active_slice,
            "slice_title": state["title"] or roadmap_item.get("title", ""),
            "slice_dir": str(slice_dir(active_milestone, active_slice)),
            "roadmap_file": roadmap_item.get("roadmap", ""),
            "selection_reason": "active execution-ready slice in .gsd/STATE.md",
        }

    active_roadmap = MILESTONES_ROOT / active_milestone / f"{active_milestone}-ROADMAP.md"
    candidate_roadmaps = []
    if active_milestone and active_roadmap.exists():
        candidate_roadmaps.append(active_roadmap)
    candidate_roadmaps.extend(path for path in roadmap_files() if path not in candidate_roadmaps)

    for path in candidate_roadmaps:
        milestone_id = path.parent.name
        if milestone_id in completed_milestones:
            continue
        for item in parse_roadmap(path):
            if not item["complete"] and slice_ready_for_implementation(
                item["milestone"], item["slice"], completed_milestones
            ):
                return {
                    "milestone_id": item["milestone"],
                    "slice_id": item["slice"],
                    "slice_title": item["title"],
                    "slice_dir": str(slice_dir(item["milestone"], item["slice"])),
                    "roadmap_file": item["roadmap"],
                    "selection_reason": "first unchecked execution-ready slice",
                }

    for directory in sorted(MILESTONES_ROOT.glob("*/slices/S*")) if MILESTONES_ROOT.exists() else []:
        milestone_id = directory.parents[1].name
        slice_id = directory.name
        if slice_ready_for_implementation(milestone_id, slice_id, completed_milestones):
            return {
                "milestone_id": milestone_id,
                "slice_id": slice_id,
                "slice_title": "",
                "slice_dir": str(directory),
                "roadmap_file": "",
                "selection_reason": "slice directory with local task plans",
            }

    return None

def main():
    selected = select_implementation_slice()
    if not selected:
        write_outputs(
            has_incomplete="false",
            milestone_id="",
            slice_id="",
            slice_title="",
            slice_dir="",
            roadmap_file="",
            selection_reason="",
        )
        print("No execution-ready GSD slice found under .gsd.")
    else:
        write_outputs(has_incomplete="true", **selected)
        print(
            "Selected GSD slice ready for implementation: "
            f"{selected['milestone_id']}/{selected['slice_id']} "
            f"{selected['slice_title']} ({selected['selection_reason']})"
        )

if __name__ == "__main__":
    main()
