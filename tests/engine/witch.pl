% example from http://www.csse.monash.edu.au/~lloyd/tildeLogic/Prolog.toy/Examples/

witch(X)  :- burns(X), female(X).
burns(X)  :- wooden(X).
wooden(X) :- floats(X).
floats(X) :- sameweight(duck, X).

female(girl).
sameweight(duck,girl).

% Query:
% witch(girl)
