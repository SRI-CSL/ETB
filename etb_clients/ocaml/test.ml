
let main () =
  let etb = Etb.init "localhost" 26532 in
  print_string "OK\n"; flush stdout;
  let f = Etb.put_file etb "etb.mli" "etb.mli" in
  print_string "OK\n"; flush stdout;
  Printf.printf "Fileref: %s\n" (Etb.string_of_value f);
  let q = Etb.query etb "in_range(1,4,X)" in
  Etb.query_wait etb q;
  let r = Etb.query_answers etb q in
  List.iter (fun m ->
    Printf.printf "Substitution:\n";
    Etb.SMap.iter (fun k v -> 
      Printf.printf "  %s: %s\n" k (Etb.string_of_value v)) m) r;
  List.iter (fun c -> Printf.printf "%s\n" c) (Etb.query_claims etb q);
  List.iter (fun c -> Printf.printf "%s\n" c) (Etb.query_all_claims etb q);
  Etb.close etb ;;

main () ;;
