#include <stdio.h>

#include "component1.h"
#include "component2.h"

int main(void)
{
  printf("3 + 2 = %d\n", f1(3,2));
  printf("3 - 2 = %d\n", f2(3,2));
  return 0;
}
