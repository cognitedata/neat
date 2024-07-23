

export function getSelectedWorkflowName() {
  let workflowName = localStorage.getItem("selectedWorkflowName");
  return workflowName;
}
export function setSelectedWorkflowName(workflowName: string) {
  localStorage.setItem("selectedWorkflowName", workflowName);
}

export function getNeatApiRootUrl() {
  let url = localStorage.getItem("neatApiRootUrl");
  if (url == null) {
    const protocol = window.location.protocol;
    const domain = window.location.hostname;
    const port = window.location.port;
    url = protocol + "//" + domain + ":" + port;
    if (url == "http://localhost:3000") {
      url = "http://localhost:8000";
    }
  }
  return url;
}

export function convertMillisToStr(millis) {
  const date = new Date(millis);
  const isoString = date.toISOString();
  return isoString;
}

export function getShortenedString(str,len) {
  str = RemoveNsPrefix(str);
  if (str.length <= len) {
    return str;
  } else {
    return str.slice(0,len)+"..."+ str.slice(-len);
  }
}

export default function RemoveNsPrefix(strWithPrefix: string) {

  if (strWithPrefix.includes("#"))
  {
    const strPlit = strWithPrefix.split("#")
    if (strPlit.length > 1) {
      return strPlit[1]
    }
  }else if (strWithPrefix.includes("/")) {
    const strPlit = strWithPrefix.split("/")
    if (strPlit.length > 1) {
      return strPlit[strPlit.length-1]
    }
  }

  return strWithPrefix;
}
