"""Bounded versioned JSON bytecode format for the verified lexical-slot VM.

SHA-256 detects accidental corruption; it is NOT authentication/signing.
Only structural verification permits execution. No pickle, eval or exec.
"""
import hashlib
import hmac
import json
import re

from .typed_function_compiler import FunctionType
from .lexical_slot_verifier import (
    BytecodeError, SlotInfo, SlotCode, VerifiedProgram,
    compile_slots, verify_slots, run_slots,
)

MAGIC = "CHRIS-VM-SLOT"
VERSION = 1
MAX_BYTES = 131072
MAX_DEPTH = 40
MAX_CODES = 256
MAX_OPS = 8192


class WireFormatError(ValueError):
    """Incorrect checksum, incompatible version, schema or typed bytecode."""


def _canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _integer(value, *, nonnegative=False):
    if type(value) is not int or len(str(abs(value))) > 80 or (
        nonnegative and value < 0
    ):
        raise WireFormatError("invalid integer")
    return value


def _array(obj, maximum=MAX_OPS):
    if type(obj) is not list or len(obj) > maximum:
        raise WireFormatError("invalid bounded array")
    return obj


def _fields(obj, keys):
    if type(obj) is not dict or set(obj) != set(keys):
        raise WireFormatError("invalid object fields")
    return obj


def _typ(value, *, decode=False, depth=0):
    if depth > MAX_DEPTH:
        raise WireFormatError("type nesting limit")
    if decode:
        value = _array(value, 3)
        if len(value) == 2 and value[0] == "base" and type(value[1]) is str and value[1] in ("Int","Rat","Bool"):
            return value[1]
        if len(value) == 3 and value[0] == "fn":
            return FunctionType(tuple(_typ(x,decode=True,depth=depth+1)
                                      for x in _array(value[1],64)),
                                _typ(value[2],decode=True,depth=depth+1))
    else:
        if type(value) is str and value in ("Int","Rat","Bool"):
            return ["base",value]
        if isinstance(value,FunctionType):
            return ["fn",[_typ(x,depth=depth+1) for x in value.arguments],
                    _typ(value.result,depth=depth+1)]
    raise WireFormatError("invalid type descriptor")


def _slot(value, *, decode=False, depth=0):
    if decode:
        value = _array(value, 5)
        if (len(value) != 5 or type(value[0]) is not str or
            not re.fullmatch("[A-Za-z_][A-Za-z0-9_]{0,79}",value[0]) or
            any(type(x) is not bool for x in value[2:])):
            raise WireFormatError("invalid slot record")
        return SlotInfo(value[0],_typ(value[1],decode=True,depth=depth+1),
                        value[2],value[3],value[4])
    if (not isinstance(value,SlotInfo) or type(value.name) is not str or
        not re.fullmatch("[A-Za-z_][A-Za-z0-9_]{0,79}",value.name) or
        any(type(x) is not bool for x in
            (value.writable,value.recursive,value.initialized))):
        raise WireFormatError("invalid slot")
    return [value.name,_typ(value.typ,depth=depth+1),
            value.writable,value.recursive,value.initialized]


def _block(value, *, decode=False, depth=0, counts=None, seen=None):
    if depth > MAX_DEPTH:
        raise WireFormatError("code nesting limit")
    counts = counts if counts is not None else [0,0]
    counts[0] += 1
    if counts[0] > MAX_CODES:
        raise WireFormatError("too many code objects")
    if decode:
        _fields(value,("captured","parameters","returns","ops"))
        captured = tuple(tuple(_slot(x,decode=True,depth=depth+1)
                               for x in _array(frame,256))
                         for frame in _array(value["captured"],256))
        params = tuple(_slot(x,decode=True,depth=depth+1)
                       for x in _array(value["parameters"],64))
        result = _typ(value["returns"],decode=True,depth=depth+1)
        ops = []
        for entry in _array(value["ops"]):
            entry = _array(entry,3)
            if len(entry) != 3 or type(entry[0]) is not str:
                raise WireFormatError("invalid instruction")
            op,arg,offset = entry
            if op == "CLOSURE_SLOT":
                arg = _block(arg,decode=True,depth=depth+1,counts=counts)
            elif op in ("BIND_SLOT","DECLARE_REC_SLOT"):
                arg = _slot(arg,decode=True,depth=depth+1)
            elif op in ("LOAD_SLOT","STORE_SLOT"):
                arg = tuple(_integer(x,nonnegative=True)
                            for x in _array(arg,2))
                if len(arg) != 2:
                    raise WireFormatError("invalid address length")
            elif op in ("PUSH_INT","CALL","JUMP","JUMP_IF_FALSE","INIT_REC_SLOT"):
                arg = _integer(arg,nonnegative=op!="PUSH_INT")
            elif op == "PUSH_BOOL":
                if type(arg) is not bool:
                    raise WireFormatError("invalid Boolean")
            elif arg is not None:
                raise WireFormatError("unexpected instruction argument")
            ops.append((op,arg,_integer(offset,nonnegative=True)))
        counts[1] += len(ops)
        if counts[1] > MAX_OPS:
            raise WireFormatError("too many instructions")
        return SlotCode(captured,params,result,tuple(ops))

    if not isinstance(value,SlotCode):
        raise WireFormatError("invalid code object")
    if seen is None:
        seen = set()
    if id(value) in seen:
        raise WireFormatError("shared or cyclic code object")
    seen.add(id(value))
    ops = []
    for op,arg,offset in value.instructions:
        if op == "CLOSURE_SLOT":
            payload = _block(arg,depth=depth+1,counts=counts,seen=seen)
        elif op in ("BIND_SLOT","DECLARE_REC_SLOT"):
            payload = _slot(arg,depth=depth+1)
        elif op in ("LOAD_SLOT","STORE_SLOT"):
            if type(arg) is not tuple or len(arg) != 2:
                raise WireFormatError("invalid address")
            payload = list(arg)
        elif op in ("PUSH_INT","CALL","JUMP","JUMP_IF_FALSE","INIT_REC_SLOT"):
            payload = _integer(arg,nonnegative=op!="PUSH_INT")
        elif op == "PUSH_BOOL":
            if type(arg) is not bool:
                raise WireFormatError("invalid bool immediate")
            payload = arg
        else:
            if arg is not None:
                raise WireFormatError("unexpected instruction argument")
            payload = arg
        ops.append([op,payload,_integer(offset,nonnegative=True)])
    counts[1] += len(ops)
    if counts[1] > MAX_OPS:
        raise WireFormatError("too many instructions")
    return {"captured":[[_slot(x,depth=depth+1) for x in frame]
                        for frame in value.captured],
            "parameters":[_slot(x,depth=depth+1) for x in value.parameters],
            "returns":_typ(value.returns,depth=depth+1),"ops":ops}


def dump_bytecode(program):
    """Deterministic serialization of an already verified program."""
    try:
        verify_slots(program)
        payload = {"result_type":_typ(program.result_type),
                   "code":_block(program.code)}
        envelope = {"magic":MAGIC,"version":VERSION,"payload":payload,
                    "sha256":hashlib.sha256(_canon(payload)).hexdigest()}
        result = _canon(envelope)
        if len(result) > MAX_BYTES:
            raise WireFormatError("bytecode payload exceeds budget")
        return result
    except (BytecodeError,RecursionError,TypeError,AttributeError) as exc:
        raise WireFormatError("unverifiable program") from exc


def _unique_pairs(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise WireFormatError("duplicate JSON field")
        result[key] = value
    return result


def _parse_int(raw):
    if len(raw.lstrip("-")) > 80:
        raise WireFormatError("oversized JSON integer")
    return int(raw)


def _reject_number(raw):
    raise WireFormatError("floats and nonfinite numbers unsupported")


def load_bytecode(data):
    """Strict parse, checksum, decode and CFG verification before returning."""
    if type(data) is not bytes or len(data) > MAX_BYTES:
        raise WireFormatError("expected bounded UTF-8 bytes")
    try:
        envelope = json.loads(data.decode("utf-8"),
                              object_pairs_hook=_unique_pairs,
                              parse_int=_parse_int,
                              parse_float=_reject_number,
                              parse_constant=_reject_number)
        _fields(envelope,("magic","version","payload","sha256"))
        if envelope["magic"] != MAGIC or type(envelope["version"]) is not int or envelope["version"] != VERSION:
            raise WireFormatError("unsupported wire format version")
        digest = envelope["sha256"]
        if type(digest) is not str or not re.fullmatch("[0-9a-f]{64}",digest):
            raise WireFormatError("invalid checksum field")
        payload = _fields(envelope["payload"],("result_type","code"))
        if not hmac.compare_digest(digest,hashlib.sha256(_canon(payload)).hexdigest()):
            raise WireFormatError("payload checksum mismatch")
        program = VerifiedProgram(_typ(payload["result_type"],decode=True),
                                  _block(payload["code"],decode=True))
        verify_slots(program)
        return program
    except (UnicodeDecodeError,json.JSONDecodeError,RecursionError,
            OverflowError,TypeError,AttributeError,BytecodeError) as exc:
        raise WireFormatError("invalid or unverifiable bytecode") from exc


def evaluate_wire(source, **limits):
    """Compile, serialize, validate and execute with no verifier bypass."""
    program = load_bytecode(dump_bytecode(compile_slots(source)))
    return program.result_type,run_slots(program,**limits)
