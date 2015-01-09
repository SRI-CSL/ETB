type t
type query
type value

module SMap : Map.S with type key = String.t
type substitution = value SMap.t

exception ETBError of string

val init : string -> int -> t
val close : t -> unit

val put_file : t -> string -> string -> value
val get_file : t -> value -> string -> unit

val string_of_value : value -> string

val query : t -> string -> query
val query_done : t -> query -> bool
val query_wait : t -> query -> unit

val query_answers : t -> query -> substitution list
val query_claims : t -> query -> string list
val query_all_claims : t -> query -> string list

