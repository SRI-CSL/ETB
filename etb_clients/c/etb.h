
#ifndef ETB

struct etb_struct;
typedef struct etb_struct* etb_handle;

struct json_object;
typedef struct json_object* etb_results;

etb_handle etb_init(const char * host, int port);
void etb_close(etb_handle etb);

char* etb_put_file(etb_handle etb, char* src, char* dst);
void etb_get_file(etb_handle etb, char* fileref, char* dst);

const char* etb_query(etb_handle etb, char* query);

void etb_wait(etb_handle etb, const char* qid);
int etb_done(etb_handle etb, const char* qid);

etb_results etb_answers(etb, qid);
etb_results etb_claims(etb, qid);
etb_results etb_all_claims(etb, qid);

/*
etb_results etb_wait_query(etb_handle etb, const char* qid);

int etb_results_len(etb_results res);
const char* etb_results_get_value(etb_results res, int index, char* field);
*/

#define ETB
#endif
