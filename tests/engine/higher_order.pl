% try to use some higher order features

neighbor(a, b).
neighbor(b, c).

neighbor(X, Y) :- tc(neighbor, X, Y).  % I have a wide notion of neighborhood.
tc(R, X, Y) :- R(X, Y).
tc(R, X, Y) :- R(X, Z), tc(R, Z, Y).

volatile(tc).
