#!/usr/bin/env python

import pystache
import re
import json
import codecs
import HTMLParser


def to_snake_case(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z])([A-Z])', r'\1_\2', s1).lower()


def parse_methods(methods):
    INCLUDED_CLASSES = ["ISteamUser", "ISteamFriends", "ISteamUtils", "ISteamUserStats", "ISteamMatchmaking", "ISteamNetworking", "ISteamApps", "ISteamMusic", "ISteamRemoteStorage", "ISteamInventory"]
    DEPRECATED_METHODS = ["TrackAppUsageEvent", "GetUserDataFolder", "InitiateGameConnection", "CommitPublishedFileUpdate", "CreatePublishedFileUpdateRequest", "DeletePublishedFile", "EnumeratePublishedFilesByUserAction", "EnumeratePublishedWorkshopFiles", "EnumerateUserPublishedFiles", "EnumerateUserSharedWorkshopFiles", "EnumerateUserSubscribedFiles", "FileFetch", "FilePersist", "GetFileListFromServer", "GetPublishedFileDetails", "GetPublishedItemVoteDetails", "GetUserPublishedItemVoteDetails", "PublishVideo", "PublishWorkshopFile", "ResetFileRequestState", "SetUserPublishedFileAction", "SubscribePublishedFile", "SynchronizeToClient", "SynchronizeToServer", "UnsubscribePublishedFile", "UpdatePublishedFileDescription", "UpdatePublishedFileFile", "UpdatePublishedFilePreviewFile", "UpdatePublishedFileSetChangeDescription", "UpdatePublishedFileTags", "UpdatePublishedFileTitle", "UpdatePublishedFileVisibility", "UpdateUserPublishedItemVote"]
    SKIP_METHODS = ["GetVoice", "DecompressVoice", "StartVoiceRecording", "StopVoiceRecording", "GetAvailableVoice", "GetVoiceOptimalSampleRate", "SetWarningMessageHook", "ActivateGameOverlay", "ActivateGameOverlayToUser", "ActivateGameOverlayToWebPage", "ActivateGameOverlayToStore", "SetOverlayNotificationPosition", "IsOverlayEnabled"]
    m = []
    for method in methods:
        classname = method.get("classname")
        methodname = method.get("methodname")
        methodalias = method.get("methodalias")
        if classname in INCLUDED_CLASSES and methodname not in DEPRECATED_METHODS and methodname not in SKIP_METHODS:
            method["classname_lower"] = to_snake_case(classname.replace("ISteam", "")).lower()
            if methodalias:
                method["methodname_lower"] = to_snake_case(methodalias).lower()
            else:
                method["methodname_lower"] = to_snake_case(methodname).lower()

            if method["methodname_lower"].startswith("b_"):
                method["methodname_lower"] = method["methodname_lower"].replace("b_", "")

            method["paramnames"] = []
            method["paramnames_in"] = []
            method["paramcount_out"] = 0
            if method.get("params") is not None:
                method["paramcount"] = len(method.get("params"))
                p = []
                out_array_call_params = []
                for param in method.get("params"):
                    paramname = param.get("paramname")
                    paramtype = param.get("paramtype")
                    # A struct that will be populated with data by the method
                    if param.get("out_struct") is not None:
                        param["paramtype"] = paramtype.replace(" *", "")
                        p.append(param)
                        method["paramnames"].append("&" + paramname)
                    # A string that will be populated with data by the method
                    elif param.get("out_string") is not None:
                        param["paramtypestring"] = paramtype.replace(" **", "_ptr").replace("const ", "const_").replace("class ", "class_").replace("struct ", "struct_")
                        p.append(param)
                        method["paramnames"].append(paramname)
                        method["paramcount_out"] = method["paramcount_out"] + 1
                    # An array that will be populated with data by the method
                    # The size of the array is specified by another parameter
                    elif param.get("out_array_count") is not None:
                        param["paramtype"] = paramtype.replace(" *", "").replace("const ", "").replace("class ", "")
                        param["paramtypestring"] = paramtype.replace(" *", "").replace("const ", "const_").replace("class ", "class_").replace("struct ", "")
                        p.append(param)
                        method["paramnames"].append(paramname)
                        method["paramcount_out"] = method["paramcount_out"] + 1
                    # An array to be populated by the method
                    # The size of the array is retrieved through a separate function call
                    elif param.get("out_array_call") is not None:
                        counter, function, params = param.get("out_array_call").split(",")
                        out_array_call_params.append(counter)
                        param["out_array_call_counter"] = counter
                        param["out_array_call_function"] = function
                        param["out_array_call_params"] = params
                        param["paramtype"] = paramtype.replace(" *", "").replace("class ", "")
                        p.append(param)
                        method["paramnames"].append(paramname)
                    # An array of data with a length specified by another parameter
                    elif param.get("array_count") is not None:
                        param["paramindex"] = len(method["paramnames_in"]) + 1
                        param["paramtype"] = paramtype.replace(" *", "").replace("const ", "").replace("class ", "")
                        p.insert(0, param)
                        method["paramnames"].append(paramname)
                        method["paramnames_in"].append(paramname)
                    # A "data blob" input parameter
                    elif "const char *" in paramtype or "const void *" in paramtype:
                        param["normal_param"] = True
                        param["paramindex"] = len(method["paramnames_in"]) + 1
                        param["paramtypestring"] = paramtype.replace(" *", "_ptr").replace("const ", "const_")
                        p.insert(0, param)
                        method["paramnames"].append(paramname)
                        method["paramnames_in"].append(paramname)
                    # A parameter that the method writes a return value to
                    # In this case we treat it as a Defold buffer
                    elif "char *" in paramtype or "void *" in paramtype or "uint8 *" in paramtype:
                        param["paramindex"] = len(method["paramnames_in"]) + 1
                        param["buffer_param"] = True
                        # param["paramtype"] = paramtype.replace("void *", "dmScript::LuaHBuffer *")
                        # param["paramtype"] = paramtype.replace("void *", "uint8 *")
                        p.insert(0, param)
                        method["paramnames"].append(paramname)
                        method["paramnames_in"].append(paramname)
                    # A parameter that the method writes a return value to
                    elif "char *" in paramtype or "void *" in paramtype or "uint8 *" in paramtype:
                        param["out_param"] = True
                        param["paramtypestring"] = paramtype.replace(" *", "_ptr")
                        p.insert(0, param)
                        method["paramnames"].append(paramname)
                        method["paramcount_out"] = method["paramcount_out"] + 1
                    # A parameter that the method writes a return value to
                    elif " *" in paramtype and "const" not in paramtype:
                        param["out_param"] = True
                        param["paramtype"] = paramtype.replace(" *", "").replace("class ", "")
                        param["paramtypestring"] = paramtype.replace(" *", "").replace("const ", "const_").replace("class ", "class_").replace("struct ", "")
                        p.insert(0, param)
                        method["paramnames"].append("&" + paramname)
                        method["paramcount_out"] = method["paramcount_out"] + 1
                    # A parameter that an "out_array_call" will write to
                    elif paramname in out_array_call_params:
                        param["out_array_call_param"] = True
                        p.insert(0, param)
                        method["paramnames"].append(paramname)
                    else:
                        param["normal_param"] = True
                        param["paramindex"] = len(method["paramnames_in"]) + 1
                        param["paramtypestring"] = paramtype.replace(" *", "_ptr").replace("const ", "const_").replace("class ", "class_").replace("struct ", "struct_")
                        p.insert(0, param)
                        method["paramnames"].append(paramname)
                        method["paramnames_in"].append(paramname)
                method["params"] = p
            else:
                method["paramcount"] = 0

            method["paramnames"] = ", ".join(method["paramnames"])
            method["paramnames_in"] = ", ".join(method["paramnames_in"])
            method["hasparams"] = method.get("params") is not None
            method["hasreturntype"] = method.get("returntype") != "void"
            returntype = method.get("returntype")
            if returntype is not None:
                method["returntypestring"] = returntype.replace(" *", "_ptr").replace("const ", "const_").replace("class ", "class_")
                if returntype == "SteamAPICall_t":
                    method["steamapicall"] = True
            m.append(method)
    return m


def parse_enums(enums):
    DEPRECATED_ENUMS = ["EWorkshopEnumerationType", "EWorkshopFileAction", "EWorkshopVideoProvider", "EWorkshopVote"]
    e = []
    for enum in enums:
        enumname = enum.get("enumname")
        if "::" not in enumname and enumname not in DEPRECATED_ENUMS:
            v = []
            for value in enum.get("values"):
                value["name"] = to_snake_case(value.get("name").replace("k_E", "").replace("k_e", "").replace("k_n", "")).upper().replace("__", "_")
                v.append(value)
            enum["values"] = v
            e.append(enum)
    return e


def parse_typedefs(typedefs):
    DEPRECATED_TYPEDEFS = ["PublishedFileUpdateHandle_t"]
    INTEGERS = ["int", "unsigned int", "short", "unsigned short", "unsigned char", "signed char", "uint8", "int8", "int16", "uint16", "int32", "uint32"]
    t = {}
    int = []
    int64 = []
    uint64 = []
    struct = []

    t["types"] = []
    t["int"] = int
    t["int64"] = int64
    t["uint64"] = uint64
    t["struct"] = struct

    for typedef in typedefs:
        if typedef not in DEPRECATED_TYPEDEFS:
            t["types"].append(typedef)
            type = typedef.get("type")
            if type in INTEGERS:
                int.append(typedef)
            elif type == "uint64" or type == "ulint64":
                uint64.append(typedef)
            elif type == "int64":
                int64.append(typedef)
            elif type.startswith("struct "):
                struct.append(typedef)

    return t


def parse_structs(structs, methods):
    SKIP_STRUCTS = ["CallbackMsg_t", "CCallbackBase", "CCallResult", "CCallback", "CSteamID", "CSteamAPIContext", "CSteamID::SteamID_t", "CSteamID::SteamID_t::SteamIDComponent_t", "CGameID::GameID_t", "CGameID::(anonymous)", "servernetadr_t", "gameserveritem_t", "SteamParamStringArray_t"]
    DEPRECATED_STRUCTS = ["RemoteStorageAppSyncedClient_t", "RemoteStorageAppSyncedServer_t", "RemoteStorageAppSyncProgress_t", "RemoteStorageAppSyncStatusCheck_t", "RemoteStorageDeletePublishedFileResult_t", "RemoteStorageEnumeratePublishedFilesByUserActionResult_t", "RemoteStorageEnumerateUserPublishedFilesResult_t", "RemoteStorageEnumerateUserSharedWorkshopFilesResult_t", "RemoteStorageEnumerateUserSubscribedFilesResult_t", "RemoteStorageEnumerateWorkshopFilesResult_t", "RemoteStorageGetPublishedFileDetailsResult_t", "RemoteStorageGetPublishedItemVoteDetailsResult_t", "RemoteStoragePublishedFileDeleted_t", "RemoteStoragePublishedFileSubscribed_t", "RemoteStoragePublishedFileUnsubscribed_t", "RemoteStoragePublishedFileUpdated_t", "RemoteStoragePublishFileProgress_t", "RemoteStoragePublishFileResult_t", "RemoteStorageSetUserPublishedFileActionResult_t", "RemoteStorageUpdatePublishedFileResult_t", "RemoteStorageUpdateUserPublishedItemVoteResult_t", "RemoteStorageUserVoteDetails_t", "SteamParamStringArray_t", ""]
    CALLRESULT_STRUCT = []

    # Include all structs that are used as a CallResult
    for method in methods:
        callresult = method.get("callresult")
        if callresult and callresult not in CALLRESULT_STRUCT:
            CALLRESULT_STRUCT.append(callresult)

    s = []
    for struct in structs:
        structname = struct.get("struct")
        if structname not in SKIP_STRUCTS and structname not in DEPRECATED_STRUCTS:
            if structname in CALLRESULT_STRUCT:
                struct["callresult"] = True
            struct["name"] = re.sub(".*::", "", structname.replace("::(anonymous)", ""))
            f = []
            for field in struct.get("fields"):
                fieldtype = field.get("fieldtype").replace("_Bool", "bool")
                # Is this an array of some kind?
                if " [" in fieldtype:
                    field["array"] = True
                    field["arraysize"] = re.match(".*\[(.*)\]", fieldtype).group(1)

                field["fieldtypestring"] = re.sub("_\[.*\]", "", fieldtype.replace(" *", "_ptr").replace("enum ", "").replace("struct ", "").replace("class ", "").replace("union ", "").replace(" ", "_"))
                f.append(field)
            struct["fields"] = f
            s.append(struct)

    return s


def parse_callbacks(methods):
    callbacks = ["PersonaStateChange_t", "GameOverlayActivated_t"]
    for method in methods:
        callback = method.get("callback")
        if callback and callback not in callbacks:
            callbacks.append(callback)

    c = []
    for callback in callbacks:
        c.append({"callback": callback})

    return c


def generate():
    j = json.load(open("steamworks/include/steam_api.json"))
    j["methods"] = parse_methods(j["methods"])
    j["typedefs"] = parse_typedefs(j["typedefs"])
    j["structs"] = parse_structs(j["structs"], j["methods"])
    j["enums"] = parse_enums(j["enums"])
    j["callbacks"] = parse_callbacks(j["methods"])

    with open("extension.mtl", 'r') as f:
        extension_mtl = f.read()
        result = pystache.render(extension_mtl, j)
        with codecs.open("steamworks/src/extension.cpp", 'wb' "utf-8") as f:
            f.write(HTMLParser.HTMLParser().unescape(result))

    with open("api.mtl", 'r') as f:
        docs_mtl = f.read()
        result = pystache.render(docs_mtl, j)
        with codecs.open("steamworks/api.md", 'wb' "utf-8") as f:
            f.write(HTMLParser.HTMLParser().unescape(result))


if __name__ == "__main__":
    generate()
