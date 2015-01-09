(* A very simple language for transition systems *)

type var = string
type const = Cbool of bool | Cint of int
type op = OPlus | OEq | OLeq | OGt | OOr | OAnd | ONot
type exp = Var of var | Const of const | Op of op * exp list
type stmt = Assign of var * exp | If of exp * stmt list * stmt list 
    | While of exp * stmt list | Prove of int * exp | Test of int * exp
type slType = Bool | Int
type program = { input : (var * slType) list;
                 output : (var * slType) list;
                 local : (var * slType) list;
                 state : (var * slType) list;
                 init : stmt list;
                 step : stmt list; }

(** The printer is not complete *)  
module Print = struct
  let rec print_list f fmt l =
    match l with
    | [] -> ()
    | [x] -> f fmt x
    | h :: t -> 
        f fmt h;
        Format.fprintf fmt "@ @,";
        print_list f fmt t

  let string_of_type t =
    match t with
    | Bool -> "bool"
    | Int -> "int"

  let vdecl fmt sec l =
    if l <> [] then begin
      Format.fprintf fmt "@[<2>%s@\n" sec;
      List.iter (function (v, t) -> 
        Format.fprintf fmt "%s : %s;@\n" v  (string_of_type t)) l;
      Format.fprintf fmt "@]@\n"
    end
    
  let rec exp fmt e =
    match e with
    | Var v -> Format.fprintf fmt "%s" v
    | Const (Cbool b) -> Format.fprintf fmt "%s" (if b then "true" else "false")
    | _ -> Format.fprintf fmt "e"

  let rec stmt fmt s =
    match s with
    | Assign (v, e) -> Format.fprintf fmt "@\n%s = %a;" v exp e
    | If (e, s1, s2) -> 
        Format.fprintf fmt "@\n@[<2>if (%a) {" exp e;
        print_list stmt fmt s1;
        Format.fprintf fmt "@]@\n@[<2>} else {";
        print_list stmt fmt s2;
        Format.fprintf fmt "@]"
    | _ -> ()

  let program oc p =
    let fmt = Format.formatter_of_out_channel oc in
    vdecl fmt "INPUT" p.input;
    vdecl fmt "OUTPUT" p.output;
    vdecl fmt "STATE" p.state;
    vdecl fmt "LOCAL" p.local;
    Format.fprintf fmt "@[<2>INIT";
    List.iter (stmt fmt) p.init;
    Format.fprintf fmt "@]@\n@\n@[<2>STEP";
    List.iter (stmt fmt) p.step;
    Format.fprintf fmt "@]@\n@."
end

(** This module does a naive SSA transformation of the program and
    translates it to a Ys.program. *)
module SSA = struct
  module VarSet = Set.Make(String)
  module VarMap = Map.Make(String)
  module Env = struct
    type t = { step : int;
               last_ids : int VarMap.t;
               next_ids : int VarMap.t;
               types : Ys.ysType VarMap.t; }

    let empty = { step=0;
                  last_ids=VarMap.empty;
                  next_ids=VarMap.empty;
                  types=VarMap.empty }

    let last_id t v = 
      if VarMap.mem v t.last_ids then VarMap.find v t.last_ids else 0
    let next_id t v = 
      if VarMap.mem v t.next_ids then VarMap.find v t.next_ids else 1
    let get_type t v = VarMap.find v t.types

    let dump t =
      Printf.printf "---------------------\n";
      VarMap.iter (fun k v -> Printf.printf "(%s %d) " k v) t.last_ids;
      Printf.printf "\n----------------------\n"

    let next t ds = 
      let t' = { step=t.step+1;
                 last_ids=VarMap.empty;
                 next_ids=VarMap.empty;
                 types=t.types } in
      let carry =
        VarMap.fold 
          (fun k v l -> (Ys.Define 
                           ({ Ys.name=k; Ys.id=0; Ys.step=t'.step },
                            get_type t k,
                            Some (Ys.Var { Ys.name=k; Ys.id=v; Ys.step=t.step })) :: l))
          t.last_ids ds in
      (t', carry)

    let update_state t ds (v, _) =
      let update = 
        Ys.Define({ Ys.name=v; Ys.id=0; Ys.step=t.step+1 }, 
                  get_type t v,
                  Some(Ys.Var { Ys.name=v; Ys.id=last_id t v; Ys.step=t.step })) in
      update :: ds

    let add_type t (v, ty) = 
      let ty' = match ty with Bool -> Ys.Bool | Int -> Ys.Int in
      { t with types = VarMap.add v ty' t.types }

    let assign t v = 
      let current = next_id t v in
      let t = 
        { t with 
          last_ids = VarMap.add v current t.last_ids;
          next_ids = VarMap.add v (current+1) t.next_ids } in
      (t, current)

    let split t t1 = { t1 with last_ids = t.last_ids }
    
    let merge t1 t2 t3 e ds =
      let emit v (t, ds) =
        if ((last_id t3 v) <> (last_id t1 v)) || ((last_id t2 v) <> (last_id t1 v)) then
          let (t, i') = assign t v in
          (t, (Ys.Define ({ Ys.name=v; Ys.id=i'; Ys.step=t1.step }, get_type t3 v,
                          Some (Ys.Ite (e, 
                                        Ys.Var ({ Ys.name=v; Ys.id=last_id t2 v; Ys.step=t1.step}), 
                                        Ys.Var ({ Ys.name=v; Ys.id=last_id t3 v; 
                                                  Ys.step=t1.step})))) :: ds))
        else
          (t, ds) in
      let candidates = VarMap.fold (fun k _ s -> VarSet.add k s) t2.last_ids VarSet.empty in
      let candidates = VarMap.fold (fun k _ s -> VarSet.add k s) t3.last_ids candidates in
      let (t, ds) = VarSet.fold emit candidates (t3, ds) in
      (t, ds)
  end

  let const = function
  | Cbool b -> Ys.Cbool b
  | Cint i -> Ys.Cint i

  let op = function
  | OPlus -> Ys.OPlus
  | OEq -> Ys.OEq
  | OLeq -> Ys.OLeq
  | OGt -> Ys.OGt
  | OOr -> Ys.OOr
  | OAnd -> Ys.OAnd
  | ONot -> Ys.ONot

  let rec exp (env:Env.t) e = 
    match e with
    | Var v -> Ys.Var ({ Ys.name=v; Ys.id=Env.last_id env v; Ys.step=env.Env.step})
    | Const c -> Ys.Const (const c)
    | Op (o, el) -> Ys.Op (op o, List.map (exp env) el)

  let rec stmt ((env, ds) : (Env.t * Ys.decl list)) s =
    match s with
    | Assign(v, e) ->
        let e = exp env e in
        let (env, i) = Env.assign env v in
        (env, (Ys.Define({Ys.name=v; Ys.id=i; Ys.step=env.Env.step}, 
                         Env.get_type env v, Some e)) :: ds)
    | If(e, s1, s2) ->
        let e = exp env e in
        let (env1, ds1) = stmts (env, ds) s1 in
        let env1' = Env.split env env1 in
        let (env2, ds2) = stmts (env1', ds1) s2 in
        Env.merge env env1 env2 e ds2
    | While(_, _) -> failwith "Not implemented yet"
    | Prove(id, e) -> 
        let e = exp env e in
        (env, (Ys.Assert (id, Ys.Op (Ys.ONot, [e]))) :: ds)
    | Test(id, e) ->
        let e = exp env e in
        (env, (Ys.Assert (id, e)) :: ds)

  and stmts (env, ds) s =
    let (env, ds) = List.fold_left stmt (env, ds) s in
    (env, ds)

  let define_input env l (v, t) =
    (Ys.Define ({ Ys.name=v; Ys.id=0; Ys.step=env.Env.step },
                Env.get_type env v, None)) :: l

  let program p = 
    let env = List.fold_left Env.add_type Env.empty p.input in
    let env = List.fold_left Env.add_type env p.output in
    let env = List.fold_left Env.add_type env p.state in
    let env = List.fold_left Env.add_type env p.local in
    let (env, ds_init) = stmts (env, []) p.init in
    let (env, ds_init) = Env.next env ds_init in
    let ds = List.fold_left (define_input env) [] p.input in
    let (env, ds) = stmts (env, ds) p.step in
    let ds = List.fold_left (Env.update_state env) ds p.state in
    { Ys.input=[];
      Ys.state=[];
      Ys.local=[];
      Ys.init = List.rev ds_init;
      Ys.transition = List.rev ds }
end
