
type mode = Check | BMC | InductiveStep
type options = { mode: mode; k: int; p: int; input: string; output: string }

let mode_of_string = function
| "check" -> Check
| "bmc" -> BMC
| "inductive" -> InductiveStep
| _ -> Printf.eprintf "Warning: invalid mode selected. Defaulting to check.\n"; Check
  
let parse_args () =
  let mode = ref "check" in
  let k = ref 1 in
  let p = ref 1 in
  let input = ref "" in
  let output = ref "" in
  Arg.parse [ "-m", Arg.Set_string mode, "mode (check, bmc, inductive)";
              "-k", Arg.Set_int k, "bmc or inductive step depth (default: 1)";
              "-p", Arg.Set_int p, "id of the property to consider";
              "-o", Arg.Set_string output, "output file" ] (fun x -> input := x) "";
  { mode=(mode_of_string !mode); k=(!k); p=(!p); input=(!input); output=(!output) }

let main() =
  let opt = parse_args() in
  let f = opt.input in
  let s = ref "" in
  let ic = open_in f in
  try
    while true do
      s := Printf.sprintf "%s\n%s" !s (input_line ic)
    done
  with
  | End_of_file -> 
      close_in ic;
      
  let p = 
    try
      Parser.program Lexer.token (Lexing.from_string !s)
    with
    | _ ->
        Printf.eprintf "Parse error on line %d\n" !Lexer.line;
        exit 1 in
  let p = Sl.SSA.program p in

  begin match opt.mode with
  | Check -> Printf.printf "checked.\n"
  | BMC -> 
      let p = Ys.Filter.program opt.p p in
      let bmc = Ys.BMC.bmc opt.k p in
      let oc = open_out opt.output in
      Ys.Print.program oc bmc;
      close_out oc
  | InductiveStep ->
      failwith "Not implemented yet"
  end;
  flush stdout;
  exit 0
;;

main () ;;

