import request from "../utils/request";

export function get_all_classes(){
    return request.get("classes/get")
}