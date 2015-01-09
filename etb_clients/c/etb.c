
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <signal.h>
#include <string.h>

#include <xmlrpc-c/base.h>
#include <xmlrpc-c/client.h>

#include <json/json.h>

#include <b64/cencode.h>
#include <b64/cdecode.h>

#include "etb.h"

struct etb_struct {
  char* url;
  xmlrpc_env env;
  xmlrpc_client* client;
};

etb_handle etb_init(const char * host, int port)
{
  char * buf = malloc(strlen(host) + 8);
  etb_handle etb = malloc(sizeof(etb_handle));
  sprintf(buf, "http://%s:%d", host, port);
  etb->url = buf;
  xmlrpc_env_init(&etb->env);
  xmlrpc_client_setup_global_const(&etb->env);
  xmlrpc_client_create(&etb->env, XMLRPC_CLIENT_NO_FLAGS, 
                       "ETB", "1.0", NULL, 0, &etb->client);
  return etb;
}

void etb_close(etb_handle etb)
{
  xmlrpc_client_event_loop_finish(etb->client);
  xmlrpc_client_destroy(etb->client);
  free(etb->url);
  free(etb);
}

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

char* etb_put_file(etb_handle etb, char* src, char* dst)
{
  xmlrpc_value* result;
  xmlrpc_value* filename;
  xmlrpc_value* sha1;
  const char* str_file;
  const char* str_sha1;
  char* fileref;

  char* file_content = get_file_content(src);
  char* coded_file = base64_encode(file_content);
  free(file_content);

  xmlrpc_client_call2f(&etb->env, etb->client, etb->url,
                       "put_file", &result, "(ss)", coded_file, dst);
  free(coded_file);
  xmlrpc_read_string(&etb->env, result, &fileref);
  return fileref;
}

void etb_get_file(etb_handle etb, char* fileref, char* dst)
{
  xmlrpc_value* result;
  char* b64_content;
  xmlrpc_client_call2f(&etb->env, etb->client, etb->url,
                       "get_file", &result, "(s)", fileref);
  xmlrpc_read_string(&etb->env, result, &b64_content);
  xmlrpc_DECREF(result);
  char* content = base64_decode(b64_content);
  FILE* fd = fopen(dst, "wb");
  fwrite(content, 1, strlen(content), fd);
  fclose(fd);
  free(b64_content);
  free(content);
}

const char* etb_query(etb_handle etb, char* query)
{
  xmlrpc_value* result;
  const char* qid;
  xmlrpc_client_call2f(&etb->env, etb->client, etb->url,
                       "eval_async", &result, "(s)", query);
  xmlrpc_read_string(&etb->env, result, &qid);
  xmlrpc_DECREF(result);
  return qid;
}

void etb_wait(etb_handle etb, const char* query)
{
  xmlrpc_value* result;
  xmlrpc_client_call2f(&etb->env, etb->client, etb->url,
                       "wait_query", &result, "(s)", query);
  xmlrpc_DECREF(result);
}

etb_results etb_answers(etb_handle etb, const char* qid)
{
  xmlrpc_value* result;
  xmlrpc_client_call2f(&etb->env, etb->client, etb->url,
                       "wait_query", &result, "(s)", query);
  xmlrpc_DECREF(result);


}



  return json;

  const char* allres;
  struct json_object *json;

  xmlrpc_read_string(&etb->env, result, &allres);
  xmlrpc_DECREF(result);
  json = json_tokener_parse(allres);

  free((void*) allres);
  return json;
}

etb_results etb_answers(etb, qid);
etb_results etb_claims(etb, qid);
etb_results etb_all_claims(etb, qid);

int etb_results_len(etb_results res)
{
  etb_results substs = json_object_object_get(res, "substs");
  return json_object_array_length(substs);
}

const char* etb_results_get_value(etb_results res, int index, char* field)
{
  etb_results substs = json_object_object_get(res, "substs");
  etb_results subst = json_object_array_get_idx(substs, index);
  etb_results value = NULL;
  int i;
  subst = json_tokener_parse(json_object_get_string(subst));
  subst = json_object_object_get(subst, "__Subst");
  for (i=0; i<json_object_array_length(subst); i++) {
    etb_results s = json_object_array_get_idx(subst, i);
    etb_results f = json_object_array_get_idx(s, 0);
    f = json_object_object_get(f, "__Var");
    if (strcmp(field, json_object_get_string(f)) == 0) {
      value = json_object_array_get_idx(s, 1);
      break;
    }
  }
  return json_object_get_string(value);
}
