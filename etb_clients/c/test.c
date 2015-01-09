#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <signal.h>

#include "etb_core.h"

int main(int const argc, const char ** const argv)
{
  query q;
  char* query = malloc(2500);
  etb_handle etb = etb_init("localhost", 26532);
  printf("OK\n");
  fileref f = etb_put_file(etb, "/Users/hamon/Work/etb/tests/short.sal", "sal.in");
  printf("Still OK\n");
  if (f == NULL) {
    exit(-1);
  }
  etb_get_file(etb, f, "back.sal");
  sprintf(query, "in_range(1,4,X)");
  free((void *) f);
  q = etb_query(etb, query);
  etb_query_wait(etb, q);
  etb_results r = etb_query_answers(etb, q);
  etb_results_iterator it;
  etb_results_iterator sIt;
  for (it = etb_results_it_start(r);
       etb_results_it_has_next(it);
       etb_results_it_next(it)) {
    for (sIt = etb_results_it_get_subst(it);
         etb_results_it_has_next(sIt);
         etb_results_it_next(sIt)) {
      printf("  %s: %s\n", etb_subst_it_get_var(sIt), etb_subst_it_get_value(sIt));
    }
  }
  free((void*) r);
  r = etb_query_claims(etb, q);
  for (it = etb_results_it_start(r);
       etb_results_it_has_next(it);
       etb_results_it_next(it)) {
    printf("  %s\n", etb_results_it_get_claim(it));
  }
  free((void*) r);
  r = etb_query_all_claims(etb, q);
  for (it = etb_results_it_start(r);
       etb_results_it_has_next(it);
       etb_results_it_next(it)) {
    printf("  %s\n", etb_results_it_get_claim(it));
  }
  free((void*) r);
  free(query);
  free((void*) q);
  etb_close(etb);
  return 0;
}
