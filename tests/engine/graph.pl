% graph and graph queries, to try slightly bigger datasets

% rules
reachable(X, Y) :- tc(edge, X, Y).

tc(R, X, Y) :- R(X, Y).
tc(R, X, Y) :- R(X, Z), tc(R, Z, Y).

cycle(X, Y) :- reachable(X, Y), reachable(Y, X).

% if we allow unsafe rules...
%path(X, X, nil).
%path(X, Y, P) :- edge(X, Y), cons(X, nil, P).
%path(X, Y, P) :- edge(X, Z), path(Z, Y, P2), cons(X, P2, P).


% graph
edge(a, b).
edge(b, c).
edge(c, d).
edge(d, e).
edge(e, f).
edge(f, g).
edge(g, h).
edge(h, i).
edge(i, j).
edge(j, k).
edge(k, l).
edge(l, m).

edge(a, m).
edge(e, b).  % small cycle is better
%edge(m, a).   meh, cycles are boring ;)
