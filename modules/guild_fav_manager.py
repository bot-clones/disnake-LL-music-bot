from __future__ import annotations
from io import BytesIO
import json
import disnake
from disnake.ext import commands
from typing import TYPE_CHECKING, Union
from utils.music.converters import URL_REG, pin_list
from utils.music.errors import GenericError
from utils.music.models import LavalinkPlayer
from utils.others import send_idle_embed
from utils.db import DBModel

if TYPE_CHECKING:
    from utils.client import BotCore


class PinManager(commands.Cog):

    def __init__(self, bot: BotCore):
        self.bot = bot

    desc_prefix = "📌 [Server Playlist] 📌 | "


    async def process_idle_embed(self, guild: disnake.Guild):
        guild_data = await self.bot.get_data(guild.id, db_name=DBModel.guilds)

        try:
            player: LavalinkPlayer = self.bot.music.players[guild.id]
            if not player.current:
                await player.process_idle_message()
            return
        except KeyError:
            pass

        try:
            channel = self.bot.get_channel(int(guild_data["player_controller"]["channel"]))
            message = await channel.fetch_message(int(guild_data["player_controller"]["message_id"]))

        except:
            return

        await send_idle_embed(message or channel, bot=self.bot, guild_data=guild_data)

    @commands.max_concurrency(1, commands.BucketType.user)
    @commands.slash_command(
        name=disnake.Localized("pin", data={disnake.Locale.pt_BR: "server_playlist"}),
        default_member_permissions=disnake.Permissions(manage_guild=True)
    )
    async def pin(self, inter: disnake.AppCmdInter):
        pass

    @pin.sub_command(
        name=disnake.Localized("add", data={disnake.Locale.pt_BR: "adicionar"}),
        description=f"{desc_prefix}Adicionar um link para lista de fixos do player."
    )
    async def add(
            self,
            inter: disnake.AppCmdInter,
            name: str = commands.Param(name="nome", description="Nome para o link."),
            url: str = commands.Param(name="link", description="Link (recomendável de playlist)."),
            description: str = commands.Param(name="descrição", description="Descrição do link.", default="")
    ):

        if "> fav:" in name.lower():
            raise GenericError("Você não pode adicionar um item incluindo esse nome: **> fav:**")

        if not URL_REG.match(url):
            raise GenericError("**Você não adicionou um link válido...**")

        if len(name) > 25:
            raise GenericError("**O nome não pode ultrapassar 25 caracteres.**")

        if len(description) > 50:
            raise GenericError("**A descrição não pode ultrapassar 50 caracteres.**")

        if len(url) > (max_url_chars:=self.bot.config["USER_FAV_MAX_URL_LENGTH"]):
            raise GenericError(f"**Quantidade máxima de caracteres permitidos no link: {max_url_chars}**")

        await inter.response.defer(ephemeral=True)

        guild_data = await self.bot.get_data(inter.guild.id, db_name=DBModel.guilds)

        if len(guild_data["player_controller"]["fav_links"]) > 25:
            raise GenericError(f"**Quantidade de links excedida! Permitido: 25.**")

        if not guild_data["player_controller"]["channel"] or not self.bot.get_channel(int(guild_data["player_controller"]["channel"])):
            raise GenericError("**Não há player configurado no servidor! Use o comando /setup**")

        guild_data["player_controller"]["fav_links"][name] = {
            "url": url,
            "description": description
        }

        await self.bot.update_data(inter.guild.id, guild_data, db_name=DBModel.guilds)

        await inter.edit_original_message(embed=disnake.Embed(description="**Link adicionado/atualizado com sucesso nos fixos do player!\n"
                         "Membros podem usá-lo diretamente no player-controller quando não estiver em uso.**", color=self.bot.get_color(inter.guild.me)))

        await self.process_idle_embed(inter.guild)

    @pin.sub_command(
        name=disnake.Localized("edit", data={disnake.Locale.pt_BR: "editar"}),
        description=f"{desc_prefix}Editar um item da lista de links fixos do servidor."
    )
    async def edit(
            self,
            inter: disnake.AppCmdInter,
            item: str = commands.Param(autocomplete=pin_list, description="item para editar."), *,
            name: str = commands.Param(name="novo_nome", default="", description="Novo nome para link."),
            url: str = commands.Param(name="novo_link", default="", description="Novo link para o item selecionado."),
            description: str = commands.Param(name="descrição", description="Descrição do link.", default="")
    ):

        if not name and not url and not description:
            raise GenericError("**Você não especificou nenhum dos itens opcionais...**")

        if "> fav:" in name.lower():
            raise GenericError("Você não deve incluir esse nome: **> fav:**")

        if len(name) > 25:
            raise GenericError("**O nome não pode ultrapassar 25 caracteres.**")

        if len(description) > 50:
            raise GenericError("**A descrição não pode ultrapassar 50 caracteres.**")

        if len(url) > (max_url_chars:=self.bot.config["USER_FAV_MAX_URL_LENGTH"]):
            raise GenericError(f"**Quantidade máxima de caracteres permitidos no link: {max_url_chars}**")

        await inter.response.defer(ephemeral=True)

        guild_data = await self.bot.get_data(inter.guild.id, db_name=DBModel.guilds)

        if not guild_data["player_controller"]["channel"] or not self.bot.get_channel(int(guild_data["player_controller"]["channel"])):
            raise GenericError("**Não há player configurado no servidor! Use o comando /setup**")

        try:
            if name:
                old_data = dict(guild_data["player_controller"]["fav_links"][item])
                del guild_data["player_controller"]["fav_links"][item]
                guild_data["player_controller"]["fav_links"][name] = {
                    'url': url or old_data["url"],
                    "description": description or old_data.get("description")
                }

            elif url:
                guild_data["player_controller"]["fav_links"][item]['url'] = url

            if description:
                guild_data["player_controller"]["fav_links"][item]['description'] = description

        except KeyError:
            raise GenericError(f"**Não há link fixo com o nome:** {item}")

        await self.bot.update_data(inter.guild.id, guild_data, db_name=DBModel.guilds)

        await inter.edit_original_message(embed=disnake.Embed(description="***Link fixo editado com sucesso!**", color=self.bot.get_color(inter.guild.me)))

        await self.process_idle_embed(inter.guild)

    @pin.sub_command(
        name=disnake.Localized("remove", data={disnake.Locale.pt_BR: "remover"}),
        description=f"{desc_prefix}Remover um link da lista de links fixos do servidor."
    )
    async def remove(
            self,
            inter: disnake.AppCmdInter,
            item: str = commands.Param(autocomplete=pin_list, description="Item para remover."),
    ):

        await inter.response.defer(ephemeral=True)

        guild_data = await self.bot.get_data(inter.guild.id, db_name=DBModel.guilds)

        try:
            del guild_data["player_controller"]["fav_links"][item]
        except:
            raise GenericError(f"**Não há links da lista com o nome:** {item}")

        await self.bot.update_data(inter.guild.id, guild_data, db_name=DBModel.guilds)

        await inter.edit_original_message(embed=disnake.Embed(description="**Link removido com sucesso!**", color=self.bot.get_color(inter.guild.me)))

        await self.process_idle_embed(inter.guild)

    @commands.cooldown(1, 20, commands.BucketType.guild)
    @pin.sub_command(
        name=disnake.Localized("import", data={disnake.Locale.pt_BR: "importar"}),
        description=f"{desc_prefix}Importar links de arq. json para a lista de links do servidor."
    )
    async def import_(
            self,
            inter: disnake.ApplicationCommandInteraction,
            file: disnake.Attachment = commands.Param(name="arquivo", description="arquivo em formato .json")
    ):

        if file.size > 2097152:
            raise GenericError("**O tamanho do arquivo não pode ultrapassar 2Mb!**")

        if not file.filename.endswith(".json"):
            raise GenericError("**Tipo de arquivo inválido!**")

        await inter.response.defer(ephemeral=True)

        try:
            data = (await file.read()).decode('utf-8')
            json_data = json.loads(data)
        except Exception as e:
            raise GenericError("**Ocorreu um erro ao ler o arquivo, por favor revise-o e use o comando novamente.**\n"
                               f"```py\n{repr(e)}```")

        for name, data in json_data.items():

            if "> fav:" in name.lower():
                continue

            if len(data['url']) > (max_url_chars := self.bot.config["USER_FAV_MAX_URL_LENGTH"]):
                raise GenericError(f"**Um item de seu arquiv ultrapassa a quantidade de caracteres permitido:{max_url_chars}\nURL:** {data['url']}")

            if len(data['description']) > 50:
                raise GenericError(f"**Um item de seu arquivo ultrapassa a quantidade de caracteres permitido:{max_url_chars}\nDescrição:** {data['description']}")

            if not isinstance(data['url'], str) or not URL_REG.match(data['url']):
                raise GenericError(f"O seu arquivo contém link inválido: ```ldif\n{data['url']}```")

        guild_data = await self.bot.get_data(inter.guild.id, db_name=DBModel.guilds)

        if not guild_data["player_controller"]["channel"] or not self.bot.get_channel(int(guild_data["player_controller"]["channel"])):
            raise GenericError("**Não há player configurado no servidor! Use o comando /setup**")

        for name in json_data.keys():
            if len(name) > (max_name_chars := 25):
                raise GenericError(f"**Um item de seu arquivo ({name}) ultrapassa a quantidade de caracteres permitido:{max_name_chars}**")
            try:
                del guild_data["player_controller"]["fav_links"][name]
            except KeyError:
                continue

        if (json_size:=len(json_data)) > 25:
            raise GenericError(f"A quantidade de itens no no arquivo excede a quantidade máxima permitida (25).")

        if (json_size + (user_favs:=len(guild_data["player_controller"]["fav_links"]))) > 25:
            raise GenericError("A lista de músicas/playlist do servidor não possui espaço suficiente para adicionar todos os itens de seu arquivo...\n"
                                f"Limite atual: 25\n"
                                f"Quantidade de links salvos: {user_favs}\n"
                                f"Você precisa de: {(json_size + user_favs)-25}")

        guild_data["player_controller"]["fav_links"].update(json_data)

        await self.bot.update_data(inter.guild.id, guild_data, db_name=DBModel.guilds)

        await inter.edit_original_message(
            embed = disnake.Embed(
                color=self.bot.get_color(inter.guild.me),
                description = "**Os links foram importados com sucesso!**\n"
                              "**Eles vão aparecer quando o player não tiver em uso ou em modo de espera.**",
            )
        )

        await self.process_idle_embed(inter.guild)

    @commands.cooldown(1, 20, commands.BucketType.guild)
    @pin.sub_command(
        name=disnake.Localized("export", data={disnake.Locale.pt_BR: "exportar"}),
        description=f"{desc_prefix}Exportar os links de músicas/playlists fixas do servidor em um arquivo json."
    )
    async def export(self, inter: disnake.ApplicationCommandInteraction):

        await inter.response.defer(ephemeral=True)

        guild_data = await self.bot.get_data(inter.guild.id, db_name=DBModel.guilds)

        if not guild_data["player_controller"]["fav_links"]:
            raise GenericError(f"**Não há músicas/playlists fixadas no servidor..\n"
                               f"Você pode adicionar usando o comando: /{self.pin.name} {self.add.name}**")

        fp = BytesIO(bytes(json.dumps(guild_data["player_controller"]["fav_links"], indent=4), 'utf-8'))

        embed = disnake.Embed(
            description=f"**Os dados dos links de músicas/playlists fixas do servidor estão aqui.\n"
                        f"Você pode importar usando o comando:** `/{self.pin.name} {self.add.name}`",
            color=self.bot.get_color(inter.guild.me))

        await inter.edit_original_message(embed=embed, file=disnake.File(fp=fp, filename="guild_favs.json"))


def setup(bot: BotCore):
    bot.add_cog(PinManager(bot))
