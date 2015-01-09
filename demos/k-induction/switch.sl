INPUT
  switch : bool;

OUTPUT
  light : bool;

STATE
  current_light : bool;
  count : int;

INIT
  current_light = false;
  count = 0;

STEP
  if (switch) {
    light = true;
    count = 1;
  } else {
    light = current_light;
    if (current_light) {
      if (count == 15) {
        light = false;
        count = 0;
      } else {
        count = count + 1;
      }
    } 
  }
  prove:1: count <= 15;
  prove:2: ((count > 0) && light) || ((count == 0) && !light);
  current_light = light;
