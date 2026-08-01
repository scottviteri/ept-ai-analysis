/- Subterm-grain sharing statistics: a Lean port of the 2019
ManipulateProofTrees hash-consing analysis (Viteri, github:ManipulateProofTrees),
applied to compiled proof terms.

For every project constant with a value (proof term / definition body), we view
the Expr as a tree and compute its maximally-shared DAG:

  dag       -- number of distinct subterms (hash-consed DAG size)
  log10tree -- log10 of the fully-expanded tree size (Float; the tree is what
               you would get by printing the term with all sharing undone --
               this is the exponential object the 2019 pipeline compressed)
  edges     -- child slots over distinct nodes (DAG edges, multiplicity kept)
  shared    -- distinct subterms referenced from >= 2 parent slots
  maxref    -- maximum reference count of any subterm
  h         -- sparse histogram {refcount: n_subterms} for refcount >= 2

Improvements over the 2019 implementation: de Bruijn indices give exact
alpha-equivalence (no positional renaming), and children keep order and
multiplicity (the original stored child *sets*).

Run from a built project root (pre-module-system toolchains):
    ... module list ... | xargs lake env lean --run analysis/subterm_stats.lean <Root>
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

def childrenOf (e : Expr) : Array Expr :=
  match e with
  | .app f a => #[f, a]
  | .lam _ t b _ => #[t, b]
  | .forallE _ t b _ => #[t, b]
  | .letE _ t v b _ => #[t, v, b]
  | .mdata _ b => #[b]
  | .proj _ _ b => #[b]
  | _ => #[]

structure DagStats where
  dag : Nat
  log10tree : Float
  edges : Nat
  shared : Nat
  maxref : Nat
  hist : List (Nat × Nat)

partial def collectNodes (root : Expr) : StateM (Std.HashMap Expr Unit × Array Expr) Unit := do
  let (seen, _) ← get
  if seen.contains root then
    return
  modify fun (s, a) => (s.insert root (), a.push root)
  for c in childrenOf root do
    collectNodes c

partial def treeSizeF (e : Expr) : StateM (Std.HashMap Expr Float) Float := do
  match (← get).get? e with
  | some v => return v
  | none =>
    let mut s : Float := 1.0
    for c in childrenOf e do
      s := s + (← treeSizeF c)
    modify fun m => m.insert e s
    return s

def dagStats (root : Expr) : DagStats := Id.run do
  let ((), (_, nodes)) := (collectNodes root).run (Std.HashMap.emptyWithCapacity, #[])
  -- reference counts: child slots over DISTINCT parents, multiplicity kept
  let mut refs : Std.HashMap Expr Nat := Std.HashMap.emptyWithCapacity
  let mut edges := 0
  for n in nodes do
    for c in childrenOf n do
      refs := refs.insert c (refs.getD c 0 + 1)
      edges := edges + 1
  let mut shared := 0
  let mut maxref := 0
  let mut histM : Std.HashMap Nat Nat := Std.HashMap.emptyWithCapacity
  for (_, k) in refs.toList do
    if k >= 2 then
      shared := shared + 1
      histM := histM.insert k (histM.getD k 0 + 1)
    if k > maxref then maxref := k
  let (ts, _) := (treeSizeF root).run (Std.HashMap.emptyWithCapacity)
  let lg := if ts.isFinite then Float.log10 ts else 999.0
  return { dag := nodes.size, log10tree := lg, edges := edges,
           shared := shared, maxref := maxref,
           hist := histM.toList }

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
    let some v := valueOf ci | continue
    let some idx := env.getModuleIdxFor? n | continue
    let modName := modNames[idx.toNat]!
    let st := dagStats v
    let kind := match ci with
      | .thmInfo _ => "theorem" | .defnInfo _ => "def" | .opaqueInfo _ => "opaque"
      | _ => "other"
    let histStr := ",".intercalate (st.hist.map fun (k, c) => s!"\"{k}\":{c}")
    IO.println s!"\{\"full\":\"{esc n.toString}\",\"file\":\"{esc modName.toString}\",\"kind\":\"{kind}\",\"dag\":{st.dag},\"log10tree\":{st.log10tree},\"edges\":{st.edges},\"shared\":{st.shared},\"maxref\":{st.maxref},\"h\":\{{histStr}}}"
    count := count + 1
  IO.eprintln s!"wrote {count} declarations"
