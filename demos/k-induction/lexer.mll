 {
   open Parser

   let line=ref 0
 }

rule token = parse
  [' ' '\t']          { token lexbuf }
| '\n'                { line := !line+1; token lexbuf }

| ';'                 { SEP }
| ':'                 { COL }
| '('                 { OP }
| ')'                 { CP }
| '{'                 { OB }
| '}'                 { CB }

| "=="                { SOP(Sl.OEq) }
| "<="                { SOP(Sl.OLeq) }
| ">"                 { SOP(Sl.OGt) }

| "||"                { SOP(Sl.OOr) }
| "&&"                { SOP(Sl.OAnd) }
| "!"                 { SOP(Sl.ONot) }

| '+'                 { SOP(Sl.OPlus) }

| '='                 { EQ }

| "true"              { BOOL(true) }
| "false"             { BOOL(false) }

| "INPUT"             { INPUT }
| "OUTPUT"            { OUTPUT }
| "LOCAL"             { LOCAL }
| "STATE"             { STATE }
| "INIT"              { INIT }
| "STEP"              { STEP }

| "bool"              { TBOOL }
| "int"               { TINT }

| "if"                { IF }
| "else"              { ELSE }
| "while"             { WHILE }
| "prove"             { PROVE }
| "test"              { TEST }

| ['0'-'9']+ as lxm   { INT(int_of_string lxm) }
| ['a'-'z''A'-'Z']['a'-'z''A'-'Z''0'-'9''_']* as lxm { IDENT(lxm) }

| eof                 { EOF }
