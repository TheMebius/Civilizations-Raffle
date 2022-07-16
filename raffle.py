# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

"""Python script to run our raffle."""

import asyncio
import base64
import collections
import contextlib
import json
import random
import subprocess
import tempfile
import time
from datetime import timezone
import datetime

import aiohttp

ADDRESS = "stars1xjzkaclgkglwhr8lc5yp3falz7ylh6806hpthw"
TEAM_WALLET = "stars1ld36u4s9cw758dpn703n5r3slttlwl6e3h4c75"
HU_WALLET = "stars14fj4wxrwgeclnjhsmd8muyzg674q7gymdf0kws"
winners_file = "data/winners.json"


KEMET_MINTER = "stars192hy2rfs0h33a6vs53pca32waulnxsg965lyrtj28dk6ecmcsd8qhvrh2w"
# COSMONAUT_MINTER = "stars18tj7yvh7qxv29wtr4angy4gqycrrj9e5j9susaes7vd4tqafzthq5h2m8r"
# STARTY_MINTER = "stars1fqsqgjlurc7z2sntulfa0f9alk2ke5npyxrze9deq7lujas7m3ss7vq2fe"
# HONOR_STARTY_MINTER = "stars19dzracz083k9plv0gluvnu456frxcrxflaf37ugnj06tdr5xhu5sy3k988"
HU_MINTER = "stars1lnrdwhf4xcx6w6tdpsghgv6uavem353gtgz77sdreyhts883wdjq52aewm"


async def get_holders(
    minter_addr: str,
    n_tokens: int,
    api_url: str = "https://rest.stargaze-apis.com/cosmwasm/wasm/v1/contract/",
):
    async with aiohttp.ClientSession() as session:
        sg721_url = f"{api_url}/{minter_addr}/smart/eyJjb25maWciOnt9fQ=="
        data = await gather_json(session, sg721_url)
        sg721 = data["data"]["sg721_address"]

        async def get_holder(token_id: int):
            query = (
                base64.encodebytes(
                    f'{{"owner_of":{{"token_id":"{token_id}"}}}}'.encode()
                )
                .decode()
                .strip()
            )
            query_url = f"{api_url}/{sg721}/smart/{query}"
            data = await gather_json(session, query_url)
            try:
                # Checking if token in team wallet, not including it in raffle
                if data["data"]["owner"] != TEAM_WALLET and data["data"]["owner"] != HU_WALLET:
                    return data["data"]["owner"]
            except KeyError:  # Token not minted yet
                return ""  # Pool wins

        tasks = [get_holder(token_id + 1) for token_id in range(n_tokens)]
        addresses = await asyncio.gather(*tasks)
        return {
            token_id: addr for token_id, addr in enumerate(addresses, start=1) if addr
        }


async def gather_json(session: aiohttp.ClientSession, url: str):
    async with session.get(url) as response:
        return await response.json()


async def get_pool_info(address, api_url="https://rest.stargaze-apis.com/cosmos"):
    """Pool value and current rewards via rest API.

    Useful links:
        https://api.akash.smartnodes.one/swagger/#/
        https://github.com/Smart-Nodes/endpoints
    """
    rewards_url = f"{api_url}/distribution/v1beta1/delegators/{ADDRESS}/rewards"

    delegated_url = f"{api_url}/staking/v1beta1/delegations/{ADDRESS}"

    async with aiohttp.ClientSession() as session:
        rewards_data, pool_data = await asyncio.gather(
            gather_json(session, rewards_url), gather_json(session, delegated_url)
        )
    rewards = float(rewards_data["rewards"][0]["reward"][0]["amount"]) / 1_000_000
    pool_value = (
        float(pool_data["delegation_responses"][0]["balance"]["amount"]) / 1_000_000
    )

    return pool_value, rewards


def get_boost(
    holder, *, kemet_counter, hu_counter
): #cosmonaut_counter, starty_counter, honor_starty_counter,
    """Probability weight boost for each cosmonaut holder."""
    # n_startys = starty_counter.get(holder, 0)
    # n_honor_startys = honor_starty_counter.get(holder, 0)
    n_planets = hu_counter.get(holder, 0)
    # n_cosmonauts = cosmonaut_counter.get(holder, 0)
    n_kemets = kemet_counter[holder]
    # Distribute other NFTs equally over all cosmonauts the holder has
    # This may currently give a fraction of an NFT to each cosmonaut, which is not an
    # issue mathematically, but does not make sense from an explorer point of view
    # TODO consider only fixed integer distribution
    # starty_boost = min(n_startys / 10 / n_kemets, 1.0)
    # honor_starty_boost = min(n_honor_startys / 10 / n_kemets, 1.0)
    planet_boost = min(n_planets / 30 / n_kemets, 1.0)
    # cosmonaut_boost = min(n_cosmonauts / 5 / n_kemets, 1.0)
    return 1.0 + planet_boost


@contextlib.contextmanager
def print_progress(*args, **kwargs):
    print("\t", *args, "...", **kwargs)
    start = time.time()
    yield
    end = time.time()
    print("\t", "...", f"done ({end - start:.2f} s)\n")

def update_winner_file(
    *,
    winner_id,
    winner_addr,
    prize,
    path: str = winners_file,
):
    data = {
        "Number": winner_id,
        "Address": winner_addr,
        "Prize": prize,
    }

    with open(path, "w") as f:
        json.dump(data, f)


async def main():
    print("Starting raffle!")
    stars_remainder = 0.0  # Extra $STARS from delayed rewards claiming
    pool_value, pool_rewards = await get_pool_info(ADDRESS)
    stars_compound = pool_rewards

    n_winners = 1
    prize = "NFT"

    print(f"    Note : {stars_compound:.2f} $STARS toward NFT mint")
    print(f"    Today's 🎁 : {prize} for {n_winners} pharaoh\n")

    with print_progress("Getting all Kemet holders"):
        kemets = await get_holders(KEMET_MINTER, 2000)
    kemet_counter = collections.Counter(kemets.values())
    print("Pharaohs total: " + str(len(kemet_counter)))

    # with print_progress("Getting all cosmonaut holders"):
    #     cosmonauts = await get_holders(COSMONAUT_MINTER, 384)
    # cosmonaut_counter = collections.Counter(cosmonauts.values())

    # with print_progress("Getting all starty holders"):
    #     startys = await get_holders(STARTY_MINTER, 1111)
    # starty_counter = collections.Counter(startys.values())

    # with print_progress("Getting all honor starty holders"):
    #     honor_startys = await get_holders(HONOR_STARTY_MINTER, 1111)
    # honor_starty_counter = collections.Counter(honor_startys.values())

    # with print_progress("Getting all HU planet holders"):
    #     hu_planets = await get_holders(HU_MINTER, 5000)
    # hu_counter = collections.Counter(hu_planets.values())
    # print("Rangers total: " + str(len(hu_counter)))

    # boosts = [
    #     get_boost(
    #         holder,
    #         # cosmonaut_counter=cosmonaut_counter,
    #         # starty_counter=starty_counter,
    #         # honor_starty_counter=honor_starty_counter,
    #         hu_counter=hu_counter,
    #         kemet_counter=kemet_counter,
    #     )
    #     for holder in kemets.values()
    # ]

    with print_progress(f"Picking {n_winners} winners"):
        winner_ids = random.choices(list(kemets))
        # winner_ids = random.choices(list(kemets), boosts) #boost for HU hodlers

        with open(winners_file,'r+') as file:
            try:
                winners = json.loads(file.read())
                file.seek(0)
                new_file = 0
            except json.JSONDecodeError:
                new_file = 1
                winners = []

            for winner_id in winner_ids:
                winner_addr = kemets[winner_id]
                print(
                    f"\n\t\tCongratulations pharaoh #{winner_id:04d} "
                )
                print(
                    "\t\tYour quest was successful!",
                    f"You found {prize} in a treasure chest",
                )
                print(f"\n\t\tWinning address: {winner_addr}")
                print("\n")

                dt = datetime.datetime.now(timezone.utc)
                utc_time = dt.replace(tzinfo=timezone.utc)
                winners.append({
                    "Raffle Time": str(utc_time),
                    "Number": winner_id,
                    "Address": winner_addr,
                    "Prize": prize,
                })

            # Write to file
            if new_file == 1:
                with open(winners_file, "w") as file:
                    json.dump(winners, file, indent=4)
            else:
            # with open("data/winners.json", "w") as f:
                json.dump(winners, file, indent=4)


if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
