    
#ifndef ETB_CORE

/** This implements the ETB core client API. */

struct etb_struct;
typedef struct etb_struct* etb_handle;

typedef const char* fileref;
typedef const char* query;
typedef const char* etb_results;

etb_handle etb_init(const char * host, int port);
void etb_close(etb_handle etb);

int etb_has_error(etb_handle etb);
const char* etb_error(etb_handle etb);

/** File access */

fileref etb_put_file(etb_handle etb, const char* src, const char* dst);
void etb_get_file(etb_handle etb, fileref f, char* dst);

/** Queries */

query etb_query(etb_handle etb, char* str_query);
int etb_query_done(etb_handle etb, query qid);
void etb_query_wait(etb_handle etb, query qid);

/** Results */

etb_results etb_query_answers(etb_handle etb, query qid);
etb_results etb_query_claims(etb_handle etb, query qid);
etb_results etb_query_all_claims(etb_handle etb, query qid);

/** Access to the results */

struct etb_results_iterator_struct;
typedef struct etb_results_iterator_struct* etb_results_iterator;

etb_results_iterator etb_results_it_start(etb_results r);
int etb_results_it_has_next(etb_results_iterator it);
void etb_results_it_next(etb_results_iterator it);

const char* etb_results_it_get_claim(etb_results_iterator it);

etb_results_iterator etb_results_it_get_subst(etb_results_iterator it);
int etb_subst_it_has_next(etb_results_iterator it);
void etb_subst_it_next(etb_results_iterator it);

const char* etb_subst_it_get_var(etb_results_iterator it);
const char* etb_subst_it_get_value(etb_results_iterator it);

#define ETB_CORE
#endif
