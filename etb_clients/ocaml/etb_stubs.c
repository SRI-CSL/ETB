#include <caml/mlvalues.h>
#include <caml/memory.h>
#include <caml/alloc.h>
#include <caml/custom.h>
#include <caml/fail.h>
#include <caml/callback.h>

#include <stdio.h>

#include "etb_core.h"

static struct custom_operations etb_ops = {
  "ETB handle",
  custom_finalize_default,
  custom_compare_default,
  custom_hash_default,
  custom_serialize_default,
  custom_deserialize_default
};

#define Etb_val(v) (*((etb_handle *) Data_custom_val(v)))

static value alloc_etb(etb_handle h)
{
  value v = alloc_custom(&etb_ops, sizeof(etb_handle), 0, 1);
  Etb_val(v) = h;
  return v;
}

value etb_stub_init(value host, value port)
{
  CAMLparam2(host, port);
  etb_handle h = etb_init(String_val(host), Int_val(port));
  CAMLreturn(alloc_etb(h));
}

value etb_stub_close(value etb)
{
  CAMLparam1(etb);
  etb_close(Etb_val(etb));
  CAMLreturn(Val_unit);
}

/** Checking for errors */
void etb_check(value etb)
{
  etb_handle h = Etb_val(etb);
  if (etb_has_error(h)) {
    caml_raise_with_string(*caml_named_value("etbError"), etb_error(h));
  }
}

/** File access */

value etb_stub_put_file(value etb, value src, value dst)
{
  CAMLparam3(etb, src, dst);
  CAMLlocal1(res);
  fileref f = etb_put_file(Etb_val(etb),
                           String_val(src),
                           String_val(dst));
  etb_check(etb);
  res = caml_copy_string(f);
  free((void*) f);
  CAMLreturn(res);
}

value etb_stub_get_file(value etb, value fileref, value dst)
{
  CAMLparam3(etb, fileref, dst);
  etb_get_file(Etb_val(etb),
               String_val(fileref),
               String_val(dst));
  etb_check(etb);
  CAMLreturn(Val_unit);
}

value etb_stub_string_of_value(value fileref)
{
  CAMLparam1(fileref);
  CAMLreturn(fileref);
}

/** Queries */

value etb_stub_query(value etb, value str_query)
{
  CAMLparam2(etb, str_query);
  CAMLlocal1(res);
  const char* q = etb_query(Etb_val(etb), String_val(str_query));
  etb_check(etb);
  res = caml_copy_string(q);
  free((void*) q);
  CAMLreturn(res);
}

value etb_stub_query_done(value etb, value query)
{
  CAMLparam2(etb, query);
  int r = etb_query_done(Etb_val(etb), String_val(query));
  etb_check(etb);
  CAMLreturn(Val_bool(r));
}

value etb_stub_query_wait(value etb, value query)
{
  CAMLparam2(etb, query);
  etb_query_wait(Etb_val(etb), String_val(query));
  etb_check(etb);
  CAMLreturn(Val_unit);
}

/** Results */

value etb_stub_query_answers(value etb, value query)
{
  CAMLparam2(etb, query);
  CAMLlocal5(in_head,in_cons,out_head, out_cons, res);
  etb_results r = etb_query_answers(Etb_val(etb), String_val(query));
  etb_results_iterator it;
  etb_results_iterator sIt;
  etb_check(etb);
  res = Val_emptylist;
  for (it = etb_results_it_start(r);
       etb_results_it_has_next(it);
       etb_results_it_next(it)) {
    out_head = Val_emptylist;
    for (sIt = etb_results_it_get_subst(it);
         etb_results_it_has_next(sIt);
         etb_results_it_next(sIt)) {
      in_head = caml_alloc_tuple(2);
      Store_field(in_head, 0, caml_copy_string(etb_subst_it_get_var(sIt)));
      Store_field(in_head, 1, caml_copy_string(etb_subst_it_get_value(sIt)));
      in_cons = caml_alloc(2,0);
      Store_field(in_cons, 0, in_head);
      Store_field(in_cons, 1, out_head);
      out_head = in_cons;
    }
    out_cons = caml_alloc(2,0);
    Store_field(out_cons, 0, out_head);
    Store_field(out_cons, 1, res);
    res = out_cons;
  }
  free((void*) r);
  CAMLreturn(res);
}

value etb_stub_query_claims(value etb, value query)
{
  CAMLparam2(etb, query);
  CAMLlocal2(res, cons);
  const char* r = etb_query_claims(Etb_val(etb), String_val(query));
  etb_results_iterator it;
  etb_check(etb);
  res = Val_emptylist;
  for (it = etb_results_it_start(r);
       etb_results_it_has_next(it);
       etb_results_it_next(it)) {
    cons = caml_alloc(2,0);
    Store_field(cons, 0, caml_copy_string(etb_results_it_get_claim(it)));
    Store_field(cons, 1, res);
    res = cons;
  }
  free((void*) r);
  CAMLreturn(res);
}

value etb_stub_query_all_claims(value etb, value query)
{
  CAMLparam2(etb, query);
  CAMLlocal2(res, cons);
  const char* r = etb_query_all_claims(Etb_val(etb), String_val(query));
  etb_results_iterator it;
  etb_check(etb);
  res = Val_emptylist;
  for (it = etb_results_it_start(r);
       etb_results_it_has_next(it);
       etb_results_it_next(it)) {
    cons = caml_alloc(2,0);
    Store_field(cons, 0, caml_copy_string(etb_results_it_get_claim(it)));
    Store_field(cons, 1, res);
    res = cons;
  }
  free((void*) r);
  CAMLreturn(res);
}
