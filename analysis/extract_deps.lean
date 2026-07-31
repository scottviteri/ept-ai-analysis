/- Kernel-grain dependency extraction.

Run from a built project root:
    lake env lean --run ../../analysis/extract_deps.lean PFR > kernel_deps.jsonl

For every constant declared in modules under the given root (e.g. `PFR`),
prints one JSON line: name, module, and the project-internal constants used
by its type and value (proof term), plus a count of external (mathlib/core)
constants used. This is the ground-truth analogue of extract_lean.py.
-/
import Lean
open Lean

def isNoise (n : Name) : Bool :=
  n.isInternal
  || n.components.any (fun c => c.toString.startsWith "_")
  || (n.toString.splitOn ".match_").length > 1
  || (n.toString.splitOn ".proof_").length > 1
  || (n.toString.splitOn ".eq_def").length > 1
  || (n.toString.splitOn "._eq_").length > 1

def esc (s : String) : String :=
  s.foldl (fun acc c =>
    acc ++ if c == '"' then "\\\"" else if c == '\\' then "\\\\" else toString c) ""

unsafe def main (args : List String) : IO Unit := do
  let rootStr := args.headD "PFR"
  let root := rootStr.toName
  initSearchPath (← findSysroot)
  -- Under the module system, proof terms live in private olean parts. They are
  -- loaded only for modules imported with `importAll := true` (per module, not
  -- transitively), and are visible only with `setExporting false`.
  let toN (s : String) : Name := (s.splitOn ".").foldl .str .anonymous
  -- args after the root: module names; a "+" prefix marks modules that have a
  -- .private.olean part (new module system) and are imported with importAll.
  let imports : Array Import :=
    if args.length > 1 then
      ((args.tail.filter (· ≠ "")).map fun s =>
        if s.startsWith "+" then
          { module := toN (s.drop 1).toString, importAll := true }
        else
          { module := toN s }).toArray
    else #[{module := root, importAll := true}]
  let env ← importModules imports {} (trustLevel := 1024)
  let env := env.setExporting false
  let modNames := env.header.moduleNames
  let inProject (n : Name) : Bool :=
    match env.getModuleIdxFor? n with
    | some idx => (modNames[idx.toNat]!).getRoot == root
    | none => false
  let mut count := 0
  for (n, ci) in env.constants.toList do
    unless inProject n && !isNoise n do continue
    let some idx := env.getModuleIdxFor? n | continue
    let modName := modNames[idx.toNat]!
    let used := ci.type.getUsedConstants
      ++ (match (ci.value? (allowOpaque := true)) with | some v => v.getUsedConstants | none => #[])
    let mut internal : List Name := []
    let mut nExternal := 0
    let mut seen : NameSet := {}
    for d in used do
      if seen.contains d then continue
      seen := seen.insert d
      if d == n then continue
      if isNoise d then continue
      if inProject d then internal := d :: internal
      else nExternal := nExternal + 1
    let kind := match ci with
      | .thmInfo _ => "theorem" | .defnInfo _ => "def"
      | .inductInfo _ => "inductive" | .ctorInfo _ => "ctor"
      | .recInfo _ => "rec" | .opaqueInfo _ => "opaque"
      | .axiomInfo _ => "axiom" | .quotInfo _ => "quot"
    let deps := ",".intercalate (internal.map (fun d => s!"\"{esc d.toString}\""))
    IO.println s!"\{\"full\":\"{esc n.toString}\",\"file\":\"{esc modName.toString}\",\"kind\":\"{kind}\",\"deps\":[{deps}],\"n_external\":{nExternal}}"
    count := count + 1
  IO.eprintln s!"wrote {count} declarations"
