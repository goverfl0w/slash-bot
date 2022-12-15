import datetime
import importlib

import naff
from beanie import PydanticObjectId
from naff.ext import paginators

import common.utils as utils
from common.const import *
from common.models import Tag


class Tags(naff.Extension):
    def __init__(self, bot: naff.Client):
        self.client = bot

    tag = naff.SlashCommand(
        name="tag",
        description="The base command for managing and viewing tags.",  # type: ignore
    )

    @tag.subcommand(
        sub_cmd_name="view",
        sub_cmd_description="Views a tag that currently exists within the database.",
    )
    @naff.slash_option(
        "tag_name",
        "The name of the tag to view.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    async def view(self, ctx: naff.InteractionContext, tag_name: str):
        if tag := await Tag.find_one(Tag.name == tag_name):
            await ctx.send(tag.description)
        else:
            raise naff.errors.BadArgument(f":x: Tag {tag_name} does not exist.")

    @tag.subcommand(
        sub_cmd_name="info",
        sub_cmd_description=(
            "Gathers information about a tag that currently exists within the database."
        ),
    )
    @naff.slash_option(
        "tag_name",
        "The name of the tag to get.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    async def info(self, ctx: naff.InteractionContext, tag_name: str):
        if not (tag := await Tag.find_one(Tag.name == tag_name)):
            raise naff.errors.BadArgument(f":x: Tag {tag_name} does not exist.")

        embed = naff.Embed(
            title=tag.name,
            color=ASTRO_COLOR,
        )

        embed.add_field("Author", f"<@{tag.author_id}>", inline=True)
        embed.add_field(
            "Timestamps",
            f"Created at: {naff.Timestamp.fromdatetime(tag.created_at).format('R')}\n"
            + (
                naff.Timestamp.fromdatetime(tag.last_edited_at).format("R")
                if tag.last_edited_at
                else "N/A"
            ),
            inline=True,
        )
        embed.add_field("Content", f"Please use {self.view.mention()}.", inline=True)
        embed.set_footer(
            "Tags are made and maintained by the Helpers here in the support server. Please contact"
            " one if you believe one is incorrect."
        )

        await ctx.send(embeds=embed)

    @tag.subcommand(
        sub_cmd_name="list", sub_cmd_description="Lists all the tags existing in the database."
    )
    async def list(self, ctx: naff.InteractionContext):
        await ctx.defer()

        all_tags = await Tag.find_all().to_list()
        # generate the string summary of each tag
        tag_list = [f"` {i+1} ` {t.name}`" for i, t in enumerate(all_tags)]
        # get chunks of tags, each of which have 10 tags
        chunks = [tag_list[x : x + 10] for x in range(0, len(tag_list), 10)]
        # finally, make embeds for each chunk of tags
        embeds = [
            naff.Embed(
                title="Tag List",
                description="This is the list of currently existing tags.",
                color=ASTRO_COLOR,
                fields=[naff.EmbedField(name="Names", value="\n".join(c))],
            )
            for c in chunks
        ]

        if len(embeds) == 1:
            await ctx.send(embeds=embeds)
            return

        pag = paginators.Paginator.create_from_embeds(self.bot, *embeds, timeout=300)
        pag.show_select_menu = True
        await pag.send(ctx)

    @tag.subcommand(
        sub_cmd_name="create", sub_cmd_description="Creates a tag and adds it into the database."
    )
    @utils.helpers_only()
    async def create(self, ctx: naff.InteractionContext):
        create_modal = naff.Modal(
            "Create new tag",
            [
                naff.ShortText(
                    "What do you want the tag to be named?",
                    placeholder="d.py cogs vs. i.py extensions",
                    custom_id="tag_name",
                    min_length=1,
                    max_length=100,
                ),
                naff.ParagraphText(
                    "What do you want the tag to include?",
                    placeholder="(Note: you can also put codeblocks in here!)",
                    custom_id="tag_description",
                    min_length=1,
                    max_length=2000,
                ),
            ],
            custom_id="astro_new_tag",
        )

        await ctx.send_modal(create_modal)
        await ctx.send("Modal sent.", ephemeral=True)

    @tag.subcommand(
        sub_cmd_name="edit",
        sub_cmd_description="Edits a tag that currently exists within the database.",
    )
    @utils.helpers_only()
    @naff.slash_option(
        "tag_name",
        "The name of the tag to edit.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    async def edit(self, ctx: naff.InteractionContext, tag_name: str):
        if not (tag := await Tag.find_one(Tag.name == tag_name)):
            raise naff.errors.BadArgument(f":x: Tag {tag_name} does not exist.")

        edit_modal = naff.Modal(
            "Edit tag",
            [
                naff.ShortText(
                    "What do you want the tag to be named?",
                    value=tag.name,
                    placeholder="d.py cogs vs. i.py extensions",
                    custom_id="tag_name",
                    min_length=1,
                    max_length=100,
                ),
                naff.ParagraphText(
                    "What do you want the tag to include?",
                    value=tag.description,
                    placeholder="(Note: you can also put codeblocks in here!)",
                    custom_id="tag_description",
                    min_length=1,
                    max_length=2000,
                ),
            ],
            custom_id=f"astro_edit_tag_{str(tag.id)}",
        )
        await ctx.send_modal(edit_modal)
        await ctx.send("Modal sent.", ephemeral=True)

    async def add_tag(self, ctx: naff.ModalContext):
        tag_name = ctx.responses["tag_name"]
        if await Tag.find_one(Tag.name == tag_name).exists():
            return await ctx.send(
                f":x: Tag `{tag_name}` already exists.\n(Did you mean to use"
                f" {self.edit.mention()}?)",
                ephemeral=True,
            )

        await Tag(
            name=tag_name,
            author_id=str(ctx.author.id),
            description=ctx.responses["tag_description"],
            created_at=datetime.datetime.now(),
        ).insert()

        await ctx.send(
            f":heavy_check_mark: `{tag_name}` now exists. In order to view it, please use"
            f" {self.view.mention()}.",
            ephemeral=True,
        )

    async def edit_tag(self, ctx: naff.ModalContext):
        tag_id = ctx.custom_id.removeprefix("astro_edit_tag_")

        if tag := await Tag.get(PydanticObjectId(tag_id)):
            tag_name = ctx.responses["tag_name"]

            original_name = tag.name
            tag.name = tag_name
            tag.description = ctx.responses["tag_description"]
            tag.last_edited_at = datetime.datetime.now()
            await tag.save()

            await ctx.send(
                (
                    f":heavy_check_mark: Tag `{tag_name}` has been edited."
                    if tag_name == original_name
                    else (
                        f":heavy_check_mark: Tag `{original_name}` has been edited and re-named to"
                        f" `{tag_name}`."
                    )
                ),
                ephemeral=True,
            )
        else:
            await ctx.send(":x: The original tag could not be found.", ephemeral=True)

    @naff.listen("modal_completion")
    async def modal_tag_handling(self, event: naff.events.ModalCompletion):
        ctx = event.ctx

        if ctx.custom_id == "astro_new_tag":
            await self.add_tag(ctx)

        elif ctx.custom_id.startswith("astro_edit_tag"):
            await self.edit_tag(ctx)

    @tag.subcommand(
        sub_cmd_name="delete",
        sub_cmd_description="Deletes a tag that currently exists within the database.",
    )
    @utils.helpers_only()
    @naff.slash_option(
        "tag_name",
        "The name of the tag to delete.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    async def delete(self, ctx: naff.InteractionContext, tag_name: str):
        await ctx.defer(ephemeral=True)

        if tag := await Tag.find_one(Tag.name == tag_name):
            await tag.delete()

            await ctx.send(
                f":heavy_check_mark: Tag `{tag_name}` has been successfully deleted.",
                ephemeral=True,
            )
        else:
            raise naff.errors.BadArgument(f":x: Tag {tag_name} does not exist.")

    @view.autocomplete("tag_name")
    @info.autocomplete("tag_name")
    @edit.autocomplete("tag_name")
    @delete.autocomplete("tag_name")
    async def tag_name_autocomplete(self, ctx: naff.AutocompleteContext, tag_name: str, **kwargs):
        if not tag_name:
            await ctx.send(
                [{"name": tag.name, "value": tag.name} async for tag in Tag.find_all(limit=25)]
            )
        else:
            choices: list[dict[str, str]] = []

            async for tag in Tag.find_all():
                if tag_name.lower() in tag.name.lower():
                    choices.append({"name": tag.name, "value": tag.name})

                if len(choices) >= 25:
                    break

            await ctx.send(choices)  # type: ignore


def setup(bot):
    importlib.reload(utils)
    Tags(bot)
