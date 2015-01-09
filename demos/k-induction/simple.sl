INPUT
  tic : bool;

OUTPUT
  out : bool;

STATE
  s : int;
  so : bool;

INIT
  s = 0;
  so = false;

STEP
  if (s == 4) {
    s = 0;
  } else {
    s = s+1;
  }

  if (s == 0) {
    so = false;
  }
  if (s == 4) {
    so = true;
  }

  out = so;

  prove:1: !((s == 0) && out);
  prove:2: !((s == 3) && out);
