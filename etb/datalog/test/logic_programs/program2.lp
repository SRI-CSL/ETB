path(X,Y) :- edge(X,Y).
path(X,Y) :- edge(X,Z), path(Z,Y).

edge(a,b).
edge(b,c).

