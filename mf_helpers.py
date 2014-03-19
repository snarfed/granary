## function to get bare urls
def just_urls_plz(org_list):
    urls = []
    for item in org_list:
        if isinstance(item, basestring):
            urls.append(item)
        else:
            itemtype = [x for x in item.get('type',[]) if x.startswith('h-')]

            if itemtype is not []:
                urls.extend(item.get('properties',{}).get('url',[]))

    return urls
