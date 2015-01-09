
type var = { name: string; id: int; step: int }
type const = Cbool of bool | Cint of int
type ysType = Bool | Int

type op = OPlus | OEq | OLeq | OGt | OOr | OAnd | ONot

type exp = Not_yet | Var of var | Const of const 
           | Op of op * exp list | Ite of exp * exp * exp
type decl = Define of var * ysType * exp option | Assert of int * exp

type program = { 
  input: var list;
  state: var list;
  local: var list;
  init: decl list;
  transition: decl list }

let empty = { input=[]; state=[]; local=[]; init=[]; transition=[] }

let concat_programs p1 p2 =
  { input = p1.input @ p2.input;
    state = p1.state @ p2.state;
    local = p1.local @ p2.local;
    init = p1.init @ p2.init;
    transition = p1.transition @ p2.transition }

module Filter = struct
  let decl id acc d =
    match d with
    | Assert (id', _) when id <> id' -> acc 
    | _ -> d :: acc

  let program id p =
    { p with transition = List.rev (List.fold_left (decl id) [] p.transition) }
end

module NegateProp = struct
  let decl d =
    match d with
    | Assert (id, e) -> Assert (id, Op(ONot, [e]))
    | _ -> d

  let program p = { p with transition=List.map decl p.transition }
end

module Unfold = struct
  let var_for_step n v = 
    match v.step with
    | 0 -> { v with step=n-1 }
    | 1 -> { v with step=n }
    | 2 -> { v with step=n+1 }
    | _ -> assert false

  let rec exp_for_step n e =
    match e with
    | Not_yet | Const _ -> e
    | Var v -> Var (var_for_step n v)
    | Op (o, el) -> Op (o, List.map (exp_for_step n) el)
    | Ite (e1, e2, e3) -> Ite (exp_for_step n e1, exp_for_step n e2, exp_for_step n e3)

  let decl_for_step n d =
    match d with
    | Define (v,t,None) -> Define (var_for_step n v, t, None)
    | Define (v,t,Some e) -> Define (var_for_step n v, t, Some (exp_for_step n e))
    | Assert (id, e) -> Assert (id, exp_for_step n e)

  let for_step n p =
    let input = List.map (var_for_step n) p.input in
    let state = List.map (var_for_step n) p.state in
    let local = List.map (var_for_step n) p.local in
    let transition = List.map (decl_for_step n) p.transition in
    { input; state; local; init=[]; transition }
end

module FreeInit = struct
  let decl d =
    match d with
    | Define (v, t, Some _) -> Define (v, t, None)
    | _ -> d

  let program p = { p with init=List.map decl p.init }
end

module BMC = struct
  let bmc n p =
    let rec unfold_all l n =
      match n with
      | 1 -> p :: l
      | _ -> unfold_all ((Unfold.for_step n p) :: l) (n-1) in
    let l_step = unfold_all [] n in
    List.fold_left concat_programs empty l_step
end

module Induction = struct
  let induction n p =
    let valid_p = NegateProp.program p in
    let valid_kp = BMC.bmc n valid_p in
    let valid_kp = FreeInit.program valid_kp in
    concat_programs valid_kp (Unfold.for_step (n+1) p)
end

module Print = struct
  let rec print_list f fmt l =
    match l with
    | [] -> ()
    | [x] -> f fmt x
    | h :: t -> 
        f fmt h;
        Format.fprintf fmt "@ @,";
        print_list f fmt t

  let string_of_op o =
    match o with
    | OPlus -> "+"
    | OEq -> "="
    | OLeq -> "<="
    | OGt -> ">"
    | OOr -> "or"
    | OAnd -> "and"
    | ONot -> "not"

  let string_of_type t =
    match t with
    | Bool -> "bool"
    | Int -> "int"

  let var fmt v = Format.fprintf fmt "%s__%d__%d" v.name v.id v.step

  let const fmt c =
    match c with
    | Cbool b -> Format.fprintf fmt "%s" (if b then "true" else "false")
    | Cint i -> Format.fprintf fmt "%d" i

  let rec exp fmt e = 
    match e with
    | Not_yet -> Format.fprintf fmt "not_yet"
    | Var v -> var fmt v
    | Const c -> const fmt c
    | Op (o, el) -> Format.fprintf fmt "@[<2>(%s@ @,%a)@]" (string_of_op o) (print_list exp) el
    | Ite (e1, e2, e3) ->
        Format.fprintf fmt "@[<2>(ite@ @,%a@ @,%a@ @,%a)@]@," exp e1 exp e2 exp e3

  let decl fmt d =
    match d with
    | Define (v, t, None) ->
        Format.fprintf fmt "@[<2>(define %a::%s)@]@\n" var v (string_of_type t)
    | Define (v, t, Some e) ->
        Format.fprintf fmt "@[<2>(define %a::%s %a)@]@\n" var v (string_of_type t) exp e
    | Assert (_, e) ->
        Format.fprintf fmt "@[<2>(assert %a)@]@\n" exp e

  let program oc p =
    let fmt = Format.formatter_of_out_channel oc in
    List.iter (decl fmt) p.init;
    List.iter (decl fmt) p.transition;
    Format.fprintf fmt "@\n(check)@\n@."
end
