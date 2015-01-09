
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <signal.h>
#include <string.h>

#include <xmlrpc-c/base.h>
#include <xmlrpc-c/client.h>

#include <b64/cencode.h>
#include <b64/cdecode.h>

#include <json/json.h>

#include "etb_core.h"

struct etb_struct {
  char* url;
  xmlrpc_env env;
  xmlrpc_client* client;
};

etb_handle etb_init(const char * host, int port)
{
  etb_handle etb = malloc(sizeof(etb_handle));
  etb->url = malloc(strlen(host) + 20);
  sprintf(etb->url, "http://%s:%d", host, port);
  xmlrpc_env_init(&etb->env);
  xmlrpc_client_setup_global_const(&etb->env);
  xmlrpc_client_create(&etb->env, XMLRPC_CLIENT_NO_FLAGS, 
                       "ETB", "1.0", NULL, 0, &etb->client);
  if (etb->env.fault_occurred) {
    printf("Error occurred\n");
    return NULL;
  }
  return etb;
}

void etb_close(etb_handle etb)
{
  xmlrpc_client_event_loop_finish(etb->client);
  xmlrpc_client_destroy(etb->client);
  free(etb->url);
  free(etb);
}

/** Error handling */

int etb_has_error(etb_handle etb)
{
  return etb->env.fault_occurred;
}

const char* etb_error(etb_handle etb)
{
  return etb->env.fault_string;
}

/** File access */

char* get_file_content(const char* filename)
{
  int size;
  FILE* fd = fopen(filename, "rb");
  fseek(fd, 0, SEEK_END);
  size = ftell(fd);
  fseek(fd, 0, SEEK_SET);
  char* buffer = malloc(size+1);
  fread(buffer, 1, size, fd);
  fclose(fd);
  buffer[size] = 0;
  return buffer;
}

char* base64_encode(const char* input)
{
  base64_encodestate state;
  char* coded = malloc(strlen(input) * 2);
  base64_init_encodestate(&state);
  int n = base64_encode_block(input, strlen(input), coded, &state);
  base64_encode_blockend(coded+n, &state);
  return coded;
}

char* base64_decode(const char* input)
{
  base64_decodestate state;
  char* out = malloc(strlen(input));
  base64_init_decodestate(&state);
  int n = base64_decode_block(input, strlen(input), out, &state);
  return out;
}

fileref etb_put_file(etb_handle etb, const char* src, const char* dst)
{
  xmlrpc_value* result;
  fileref f;

  char* file_content = get_file_content(src);
  char* coded_file = base64_encode(file_content);
  free(file_content);
  xmlrpc_client_call2f(&etb->env, etb->client, etb->url,
                       "put_file", &result, "(ss)", coded_file, dst);
  free(coded_file);
  if (etb->env.fault_occurred) {
    return NULL;
  }
  xmlrpc_read_string(&etb->env, result, &f);
  xmlrpc_DECREF(result);
  return f;
}

void etb_get_file(etb_handle etb, fileref f, char* dst)
{
  xmlrpc_value* result;
  const char* b64_content;
  xmlrpc_client_call2f(&etb->env, etb->client, etb->url,
                       "get_file", &result, "(s)", f);
  if (etb->env.fault_occurred) {
    return;
  }
  xmlrpc_read_string(&etb->env, result, &b64_content);
  xmlrpc_DECREF(result);
  char* content = base64_decode(b64_content);
  FILE* fd = fopen(dst, "wb");
  fwrite(content, 1, strlen(content), fd);
  fclose(fd);
  free((char*) b64_content);
  free(content);
}

/** Queries */

query etb_query(etb_handle etb, char* str_query)
{
  xmlrpc_value* result;
  query qid;
  xmlrpc_client_call2f(&etb->env, etb->client, etb->url,
                       "query", &result, "(s)", str_query);
  if (etb->env.fault_occurred) {
    return NULL;
  }
  xmlrpc_read_string(&etb->env, result, &qid);
  xmlrpc_DECREF(result);
  return qid;
}

int etb_query_done(etb_handle etb, query q)
{
  xmlrpc_value* result;
  xmlrpc_bool b;
  
  xmlrpc_client_call2f(&etb->env, etb->client, etb->url,
                       "query_done", &result, "(s)", q);
  if (etb->env.fault_occurred) {
    return -1;
  }
  xmlrpc_read_bool(&etb->env, result, &b);
  xmlrpc_DECREF(result);
  return b;
}

void etb_query_wait(etb_handle etb, query q)
{
  xmlrpc_value* result;
  xmlrpc_client_call2f(&etb->env, etb->client, etb->url,
                       "query_wait", &result, "(s)", q);
  if (etb->env.fault_occurred) {
    return;
  }
  xmlrpc_DECREF(result);
}

/** Results */

etb_results etb_query_answers_generic(etb_handle etb, 
                                      query qid, 
                                      const char* method)
{
  xmlrpc_value* result;
  const char* str_results;
  xmlrpc_client_call2f(&etb->env, etb->client, etb->url,
                       method, &result, "(s)", qid);
  if (etb->env.fault_occurred) {
    return NULL;
  }
  xmlrpc_read_string(&etb->env, result, &str_results);
  xmlrpc_DECREF(result);
  return str_results;
}

etb_results etb_query_answers(etb_handle etb, query qid)
{
  return etb_query_answers_generic(etb, qid, "query_answers");
}

etb_results etb_query_claims(etb_handle etb, query qid)
{
  return etb_query_answers_generic(etb, qid, "query_claims");
}

etb_results etb_query_all_claims(etb_handle etb, query qid)
{
  return etb_query_answers_generic(etb, qid, "query_all_claims");
}

/** Access to the results */

struct etb_results_iterator_struct {
  json_object* json;
  int num_elements;
  int current_element;
};

etb_results_iterator etb_results_it_start(etb_results r)
{
  etb_results_iterator it = malloc(sizeof(etb_results_iterator));
  it->json = json_tokener_parse(r);
  it->num_elements = json_object_array_length(it->json);
  it->current_element = 0;
  return it;
}

int etb_results_it_has_next(etb_results_iterator it)
{
  return it->current_element < it->num_elements;
}

void etb_results_it_next(etb_results_iterator it)
{
  it->current_element++;
}

const char* etb_results_it_get_claim(etb_results_iterator it)
{
  json_object* c = json_object_array_get_idx(it->json, it->current_element);
  return json_object_get_string(c);
}

etb_results_iterator etb_results_it_get_subst(etb_results_iterator it)
{
  etb_results_iterator sIt = malloc(sizeof(etb_results_iterator));
  json_object* s = json_object_array_get_idx(it->json, it->current_element);
  json_object* ps = json_tokener_parse(json_object_get_string(s));
  sIt->json = json_object_object_get(ps, "__Subst");
  sIt->num_elements = json_object_array_length(sIt->json);
  sIt->current_element = 0;
  return sIt;
}

const char* etb_subst_it_get_var(etb_results_iterator it)
{
  json_object* s = json_object_array_get_idx(it->json, it->current_element);
  json_object* v = json_object_array_get_idx(s, 0);
  json_object* vn = json_object_object_get(v, "__Var");
  return json_object_get_string(vn);
}

const char* etb_subst_it_get_value(etb_results_iterator it)
{
  json_object* s = json_object_array_get_idx(it->json, it->current_element);
  json_object* v = json_object_array_get_idx(s, 1);
  return json_object_get_string(v);
}

