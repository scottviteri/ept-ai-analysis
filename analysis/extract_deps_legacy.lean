/- Kernel-grain dependency extraction for pre-module-system toolchains
(Lean 4.28–4.31: no `importAll` field, no public/private olean split).

Run from a built project root:
    ... module list ... | xargs lake env lean --run analysis/extract_deps_legacy.lean <Root>

Same output format as extract_deps.lean. "+"-prefixed module args are accepted
(and the prefix ignored) so the same driver works for both script variants.
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

def valueOf (ci : ConstantInfo) : Option Expr :=
  match ci with
  | .thmInfo v => some v.value
  | .defnInfo v => some v.value
  | .opaqueInfo v => some v.value
  | _ => none

unsafe def main (args : List String) : IO Unit := do
  let rootStr := args.headD "Main"
  let root := rootStr.toName
  initSearchPath (← findSysroot)
  let toN (s : String) : Name := (s.splitOn ".").foldl .str .anonymous
  let clean (s : String) : String := if s.startsWith "+" then (s.drop 1).toString else s
  let mods := if args.length > 1 then
    (args.tail.filter (· ≠ "")).map (fun s => toN (clean s)) else [root]
  let imports := mods.toArray.map fun m => { module := m : Import }
  let env ← importModules imports {} (trustLevel := 1024)
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
      ++ (match valueOf ci with | some v => v.getUsedConstants | none => #[])
    let mut internal : List Name := []
    let mut external : List Name := []
    let mut seen : NameSet := {}
    for d in used do
      if seen.contains d then continue
      seen := seen.insert d
      if d == n then continue
      if isNoise d then continue
      if inProject d then internal := d :: internal
      else external := d :: external
    let kind := match ci with
      | .thmInfo _ => "theorem" | .defnInfo _ => "def"
      | .inductInfo _ => "inductive" | .ctorInfo _ => "ctor"
      | .recInfo _ => "rec" | .opaqueInfo _ => "opaque"
      | .axiomInfo _ => "axiom" | .quotInfo _ => "quot"
    let deps := ",".intercalate (internal.map (fun d => s!"\"{esc d.toString}\""))
    let extDeps := ",".intercalate (external.map (fun d => s!"\"{esc d.toString}\""))
    IO.println s!"\{\"full\":\"{esc n.toString}\",\"file\":\"{esc modName.toString}\",\"kind\":\"{kind}\",\"deps\":[{deps}],\"n_external\":{external.length},\"ext_deps\":[{extDeps}]}"
    count := count + 1
  IO.eprintln s!"wrote {count} declarations"
