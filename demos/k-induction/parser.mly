%token <bool> BOOL
%token <int> INT

%token <string> IDENT

%token <Sl.op> SOP

%token EQ
%token OP CP OB CB COL SEP EOF
%token IF ELSE WHILE PROVE TEST

%token INPUT OUTPUT LOCAL STATE INIT STEP

%token TBOOL TINT

%start program
%type <Sl.program> program
%%
program: inputs outputs locals states init step EOF
  { { Sl.input=$1; Sl.output=$2; Sl.local=$3; Sl.state=$4; Sl.init=$5; Sl.step=$6 } } ;

inputs: INPUT var_decl_list { List.rev $2 }
      |                     { [] } ;
outputs: OUTPUT var_decl_list { List.rev $2 }
      |                     { [] } ;
locals: LOCAL var_decl_list { List.rev $2 }
      |                     { [] } ;
states: STATE var_decl_list { List.rev $2 }
      |                     { [] } ;

init: INIT stmt_list { List.rev $2 } ;
step: STEP stmt_list { List.rev $2 } ;

var_decl_list: 
  var_decl_list IDENT COL aType SEP { ($2, $4) :: $1 }
|                                    { [] } ;

stmt_list:
  stmt_list stmt { $2 :: $1 }
|                { [] } ;

stmt:
  IDENT EQ exp SEP { Sl.Assign($1, $3) }
| IF OP exp CP OB stmt_list CB { Sl.If($3, List.rev $6, []) }
| IF OP exp CP OB stmt_list CB ELSE OB stmt_list CB { Sl.If($3, List.rev($6), List.rev($10)) }
| WHILE OP exp CP OB stmt_list CB { Sl.While($3, List.rev($6)) }
| PROVE COL INT COL exp SEP { Sl.Prove($3, $5) }
| TEST COL INT COL exp SEP { Sl.Test($3, $5) } ;

exp:
  IDENT { Sl.Var($1) }
| BOOL  { Sl.Const (Sl.Cbool $1) }
| INT   { Sl.Const (Sl.Cint $1) }
| SOP exp { Sl.Op($1, [$2]) }
| exp SOP exp { Sl.Op($2, [$1; $3]) }
| OP exp CP { $2 } ;

aType:
  TBOOL { Sl.Bool }
| TINT  { Sl.Int } ;
