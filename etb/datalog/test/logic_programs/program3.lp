% we want q1(1,3) and q2(5,3) and no other q1 or q2

q1(X,Y) :- p(X,Z), r(Z,Y), lt(X,Y).
q2(X,Y) :- p(X,Z), r(Z,Y), lt(Y,X).

p(1,2).
r(2,3).
p(5,4).
r(4,3).
