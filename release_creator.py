import argparse
import requests
import re


def argParser():
    parser = argparse.ArgumentParser(description='Compare latest tags of two repos')
    parser.add_argument('--auth', type=str, help='Github authentication token', required=True)
    parser.add_argument('--target_owner_repo', type=str, help='Target owner/repo', required=True)
    parser.add_argument('--local_owner_repo', type=str, help='Local owner/repo', required=True)
    parser.add_argument('--discord_webhook', type=str, help='Discord webhook', default=None, required=False)
    return parser.parse_args()


def getLatestTag(jsonResponse):
    return jsonResponse[-1]['ref'].split('/')[-1]


def getReleases(url, owner_repo, headers):
    return requests.get(f'{url.prefix}/{owner_repo}/{url.postfix}', headers=headers)


def createRelease(url, owner_repo, headers, tag_name, name, body, target_commitish='main'):
    data = {
        'tag_name': tag_name,
        'name': name,
        'body': body,
        'target_commitish': target_commitish,
    }
    return requests.post(f'{url.prefix}/{owner_repo}/releases', json=data, headers=headers)


def sendDiscordNotification(message, webhook):
    data = {
        'content': message,
    }
    return requests.post(webhook, json=data)


def notify(message, raiseException=False, webhook=None):
    if webhook:
        sendDiscordNotification(message, webhook)

    if raiseException:
        raise Exception(message)
    else:
        print(message)


def compareTags(a, b):
    return True if a == b else False


def tagSanityCheck(version):
    return True if re.match(r'^\d{4}\.\d{2}(\.\d{0,2})?', version) else False


# https://stackoverflow.com/questions/59081778/rules-for-special-characters-in-github-repository-name#59082561
def ownerRepoSanityCheck(owner_repo):
    return True if re.match(r'^[\w.-]+\/[\w.-]+$', owner_repo) else False


# https://gist.github.com/magnetikonline/073afe7909ffdd6f10ef06a00bc3bc88
def tokenSanityCheck(token):
    pat = r'^(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}|v[0-9]\.[0-9a-f]{40})$'
    return True if re.match(pat, token) else False


def SanityCheck(auth, target_owner_repo, local_owner_repo, webhook=None):
    if not tokenSanityCheck(auth):
        notify('Auth token is not valid', raiseException=True, webhook=webhook)

    if not ownerRepoSanityCheck(target_owner_repo):
        notify('Target repo is not valid', raiseException=True, webhook=webhook)

    if not ownerRepoSanityCheck(local_owner_repo):
        notify('Local repo is not valid', raiseException=True, webhook=webhook)


def main():
    args = argParser()

    SanityCheck(args.auth, args.target_owner_repo, args.local_owner_repo, args.discord_webhook)

    AUTH_BEARER = args.auth

    HEADERS = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {AUTH_BEARER}',
        'X-GitHub-Api-Version': '2022-11-28',
    }

    URL = type('URL', (object,), {})
    setattr(URL, 'prefix', 'https://api.github.com/repos')
    setattr(URL, 'postfix', 'git/matching-refs/tags')

    latestTargetTag = getLatestTag(getReleases(URL, args.target_owner_repo, HEADERS).json())
    if not tagSanityCheck(latestTargetTag):
        notify(f'Latest tag in target repo is not valid: {latestTargetTag}',
               raiseException=True, webhook=args.discord_webhook)

    latestLocalTag = getLatestTag(getReleases(URL, args.local_owner_repo, HEADERS).json())
    if not tagSanityCheck(latestLocalTag):
        notify(f'Latest tag in local repo is not valid: {latestLocalTag}',
               raiseException=True, webhook=args.discord_webhook)

    if compareTags(latestTargetTag, latestLocalTag):
        notify('No update needed')
    else:
        notify(f'Update needed, latest is {latestTargetTag}', webhook=args.discord_webhook)
        r = createRelease(
            URL,
            args.local_owner_repo,
            HEADERS,
            latestTargetTag,
            latestTargetTag,
            f'This release was automatically generated, changes for pi-hole are available here: https://github.com/pi-hole/docker-pi-hole/releases/tag/{latestTargetTag}')

        if r.status_code == 201:
            notify('Release created', webhook=args.discord_webhook)
        else:
            notify(
                f'Release creation failed\n\tStatus code: {r.status_code}\n\tText: {r.text}',
                webhook=args.discord_webhook)


if __name__ == '__main__':
    main()
