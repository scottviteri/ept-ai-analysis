/- Kernel-grain dependency extraction via re-elaboration.

The module system strips theorem proof bodies from oleans, so post-hoc import
cannot see them. Instead, re-elaborate one source file with the frontend
(imports load from cached oleans) and read the freshly type-checked constants
from the kernel environment.

Run from a built project root, one file per invocation:
    lake env lean --run analysis/extract_deps_frontend.lean PFR/Main.lean PFR.Main

Prints one JSON line per locally-declared constant: name, kind, and every
constant its type+value reference (unfiltered; filter downstream).
-/
import Lean
open Lean Elab

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
  let file := args[0]!
  let modName := (args[1]!.splitOn ".").foldl .str .anonymous
  initSearchPath (← findSysroot)
  enableInitializersExecution
  let input ← IO.FS.readFile file
  let opts : Options := {}
  let some env ← runFrontend input opts file modName (trustLevel := 1024)
    | throw <| IO.userError s!"elaboration failed: {file}"
  let kenv := env.toKernelEnv
  let mut count := 0
  for (n, ci) in kenv.constants.map₂.toList do
    if isNoise n then continue
    let used := ci.type.getUsedConstants
      ++ (match (ci.value? (allowOpaque := true)) with | some v => v.getUsedConstants | none => #[])
    let mut seen : NameSet := {}
    let mut deps : List Name := []
    for d in used do
      if seen.contains d || d == n || isNoise d then continue
      seen := seen.insert d
      deps := d :: deps
    let kind := match ci with
      | .thmInfo _ => "theorem" | .defnInfo _ => "def"
      | .inductInfo _ => "inductive" | .ctorInfo _ => "ctor"
      | .recInfo _ => "rec" | .opaqueInfo _ => "opaque"
      | .axiomInfo _ => "axiom" | .quotInfo _ => "quot"
    let depsStr := ",".intercalate (deps.map (fun d => s!"\"{esc d.toString}\""))
    let hv := if  (ci.value? (allowOpaque := true)).isSome then "true" else "false"
    IO.println s!"\{\"full\":\"{esc n.toString}\",\"file\":\"{esc modName.toString}\",\"kind\":\"{kind}\",\"has_value\":{hv},\"deps\":[{depsStr}]}"
    count := count + 1
  IO.eprintln s!"{modName}: {count} constants"
