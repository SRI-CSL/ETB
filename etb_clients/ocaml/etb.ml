type t
type query
type value
type claim

module SMap = Map.Make(String)

type substitution = value SMap.t

exception ETBError of string
let _ = Callback.register_exception "etbError" (ETBError "string")

external init : string -> int -> t = "etb_stub_init"
external close : t -> unit = "etb_stub_close"

external put_file : t -> string -> string -> value = "etb_stub_put_file"
external get_file : t -> value -> string -> unit = "etb_stub_get_file"

external string_of_value : value -> string = "etb_stub_string_of_value"

external query : t -> string -> query = "etb_stub_query"
external query_done : t -> query -> bool = "etb_stub_query_done"
external query_wait : t -> query -> unit = "etb_stub_query_wait"

external query_answers : 
  t -> query -> (string * value) list list = "etb_stub_query_answers"
external query_claims : t -> query -> string list = "etb_stub_query_claims"
external query_all_claims : t -> query -> string list = "etb_stub_query_all_claims"

let query_answers t q =
  let l = query_answers t q in
  List.map (List.fold_left (fun m (s,v) -> SMap.add s v m) SMap.empty) l
