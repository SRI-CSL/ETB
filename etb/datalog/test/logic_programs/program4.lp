% making sure unification properly offsets the clause. The query p(X,b) should
% succeed with X = 2. The lt will however only be executed by the goal handler.
% For this the goal p(X,2) will need to match against the head.

p(1,X) :- lt(1,3).
