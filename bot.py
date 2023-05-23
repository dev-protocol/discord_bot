import os
import discord
import openai
from decouple import config
import re
import functools
import typing
import asyncio


DISCORD_TOKEN = config('DISCORD_TOKEN')
OPEN_API_KEY = config('OPENAI_API_KEY')
openai.api_key = OPEN_API_KEY

intents = discord.Intents.default()
# intents.messages = True

# turn off messages from guilds, so you only get messages from DM channels
# intents.guild_messages = False
intents.message_content = True


class ChatBot(discord.Client):

    def __init__(self, intents):
        super().__init__(intents=intents)
        self.system_prompt_dict = {}
        self.conversations = {}
        self.default_sys = ("You are BIDARA, Bio-Inspired Design and Research Assistant, and an expert in all fields of science. As a biomimetic designer, focus on understanding, learning from, and emulating the strategies used by living things, with the intention of creating designs and technologies that are sustainable.\n\n"
                            "Given a design challenge, think step-by-step through the following steps. Describe your plan written out in great detail and cite peer reviewed sources for your answers.\n\n"
                            "1. Biologize - Analyze the essential functions and context your design solution must address. Reframe them in biological terms, so that you can “ask nature” for advice. The goal of this step is to arrive at one or more “How does nature…?” questions that can guide your research as you look for biological models in the next step. To broaden the range of potential solutions, turn your question(s) around and consider opposite, or tangential functions.\n"
                            "2. Discover - Look for natural models (organisms and ecosystems) that need to address the same functions and context as your design solution. Identify the strategies used that support their survival and success. This step focuses on research and information gathering. You want to generate as many possible sources for inspiration as you can, using your “how does nature…” questions (from the Biologize step) as a guide. Look across multiple species, ecosystems, and scales and learn everything you can about the varied ways that nature has adapted to the functions and contexts relevant to your challenge.\n"
                            "3. Abstract - Carefully study the essential features or mechanisms that make the biological strategies successful. Use plain language to write down your understanding of how the features work, using sketches to ensure accurate comprehension. The goal of creating a design strategy is to make it easier to translate lessons from biology into design solutions. Design strategies describe how the biological strategy works without relying on biological terms. This makes cross-disciplinary collaboration easier because a design strategy focuses on function and mechanism without the baggage of potentially unfamiliar biological terms. Summarize the key elements of the biological strategy, capturing how it works to meet the function you’re interested in. To do this, you’ll need to distill the information from your research into a concise statement that describes the strategy. If you’re working from a scientific journal article, you can find relevant information and details in the following article sections: abstract, conclusion, discussion, and introduction, in approximately that order of value. Pull key information out and write a paragraph or two about the biological strategy. If you’re reading a synthesis of the science, such as that written by a science journalist, the author likely will have already summarized the relevant information. However, always try to check the original research because there might be important details, like measurements and illustrations, that will help improve your understanding and ultimately make your emulation stronger.")

        # TODO
        # !examples
        self.instructions = "".join(["Welcome to BIDARA, a Bio-Inspired Design and Research Assistant AI chatbot that uses OpenAI’s GPT-4 model to respond to queries.\n",
                                     "As you chat back and forth either through DMs or in #chat-with-bidara, BIDARA keeps track of all the messages between you and it as part of your unique conversation history. ",
                                     "This allows it to respond to new queries based on the context of your conversation. Eventually your conversation will need to be cleared or OpenAI will not be able to generate new responses. ",
                                     "To clear the conversation, and start a new one, use the `!clear_conv` command.\n\n",
                                     "BIDARA can be directed to respond in certain ways, by using GPT-4’s system prompt. By default the system prompt BIDARA uses allows it to respond in ways helpful for bio-inspired design and research assistant activities. ",
                                     "Please let us know about your experiences, good or bad, in the #bidara-feedback channel so we can improve it.\n\n",
                                     "**Do not share any sensitive information** in your conversations including but not limited to, personal information, ITAR, CUI, export controlled, or trade secrets.\n",
                                     "While OpenAI has safeguards in place, the chatbot may occasionally generate incorrect or misleading information and produce offensive or biased content.\n",
                                     "The chatbot may produce inaccurate information about people, places, or facts. It is not intended to give advice. Conversations may be reviewed by OpenAI's AI trainers to improve their systems.\n\n",
                                     "Here are the in-built commands:\n",
                                     "`!help` - description of bot and commands.\n",
                                     "`!example` - show an example conversation with BIDARA.\n",
                                     "`!system` - lists your current system prompt.\n",
                                     "`!set_default_sys` - set your system prompt to the default BIDARA prompt.\n",
                                     "`!set_custom_sys` - set a custom system prompt.\n",
                                     "`!clear_sys` - clear your current system prompt.\n",
                                     "`!curr_conv` - shows your current conversation.\n",
                                     "`!clear_conv` - clear your current conversation.\n",
                                     "\n\n"])

        self.example = "".join(["**Bio-inspired non-toxic white paint**\n",
                                "_user:_ How do organisms in nature reflect the color white?\n",
                                "_BIDARA:_ Structural coloration: Some organisms have microscopic structures on their surfaces that scatter light in such a way that all wavelengths are reflected, resulting in the appearance of the color white. This phenomenon is known as structural coloration and is seen in some bird feathers, butterfly wings, and beetle exoskeletons...\n",
                                "_user:_ What are some white beetles that use structural coloration?\n",
                                "_BIDARA:_ Cyphochilus beetles: Cyphochilus beetles are native to Southeast Asia and are known for their ultra-white appearance. Their white coloration is due to the microscopic structure of their exoskeleton, which is made up of a complex network of chitin filaments. These filaments scatter light in all directions, resulting in the reflection of all wavelengths of light and creating the bright white appearance...\n"])
        self.custom_sys = False

    async def on_ready(self):
        print(f'{self.user} is connected to Discord')

    def get_chatgpt_messages(self, input_content, author):
        messages = self.conversations[author]

        if author not in self.system_prompt_dict:
            self.system_prompt_dict[author] = self.default_sys
        sys_prompt = {'role': 'system',
                          'content': self.system_prompt_dict[author]}

        if messages == []:
            messages.append(sys_prompt)
        else:
            messages[0] = sys_prompt

        messages.append(
            {'role': 'user', 'content': input_content})

        self.conversations[author] = messages

    async def send_chunks(self, assistant_response, chunk_length, message):
        chunks = [assistant_response[i:i+chunk_length]
                  for i in range(0, len(assistant_response), chunk_length)]
        for chunk in chunks:
            await message.channel.send(chunk)

    def to_thread(func: typing.Callable) -> typing.Coroutine:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            wrapped = functools.partial(func, *args, **kwargs)
            return await loop.run_in_executor(None, wrapped)
        return wrapper

    @to_thread
    def call_openai(self, messages):
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages,
            temperature=0,
        )
        return response

    async def process_system_prompt(self, message):
        if message.author not in self.system_prompt_dict:
            self.system_prompt_dict[message.author] = self.default_sys
        await message.channel.send((f"This is your current system prompt:\n>>> {self.system_prompt_dict[message.author]}"))

    async def set_system_prompt(self, prompt_choice, message):
        if prompt_choice == "default":
            self.system_prompt_dict[message.author] = self.default_sys
            await message.channel.send(f"Your system prompt is set to:\n>>> {self.default_sys}\n\n")
            await message.channel.send("If you would like to change or clear it, type `!set_custom_sys` or `!clear_sys`, respectively.")
        elif prompt_choice == "custom":
            self.custom_sys = True

            def check(m):
                return m.content != "" and m.channel == message.channel

            await message.channel.send("Please type the system prompt you would like to use.")

            try:
                msg = await self.wait_for('message', timeout=200.0, check=check)
            except asyncio.TimeoutError:
                await message.channel.send("No system prompt was set.")
                return

            self.system_prompt_dict[message.author] = msg.content
            await message.channel.send(f"Your system prompt is set to:\n>>> {msg.content}")

    async def list_conv(self, message):
        curr_conversation = self.conversations[message.author]
        if curr_conversation == []:
            await message.channel.send("No conversation currently.")

        for i in curr_conversation:
            content = i["content"]
            role = i["role"]
            if role == "system" and content == "":
                content = "No system prompt set"
            await message.channel.send(role + ": " + content)

    async def process_keyword(self, keyword, message):
        if keyword == "help":
            await message.channel.send(self.instructions)
        elif keyword == "system":
            await self.process_system_prompt(message)
        elif keyword[-3:] == "sys" and keyword[:3] == "set":
            prompt_choice = keyword.split("_")[1]
            await self.set_system_prompt(prompt_choice, message)
        elif keyword == "clear_sys":
            self.system_prompt_dict[message.author] = ""
            await message.channel.send("Your system prompt for Chat-GPT is cleared.")
        elif keyword == "curr_conv":
            await self.list_conv(message)
        elif keyword == "clear_conv":
            if message.author in self.conversations:
                self.system_prompt_dict[message.author] = ""
                self.conversations[message.author] = []
                await message.channel.send("Your previous conversation is cleared.")
        elif keyword == "example":
            chunk_length = 2000
            if len(self.example) > chunk_length:
                await self.send_chunks(self.example, chunk_length, message)
            else:
                await message.channel.send(self.example)
        else:
            await message.channel.send("Not a valid commmand.")

    async def on_message(self, message):
        # Check if a message is a DM
        # if isinstance(message.channel, discord.channel.DMChannel):

        if message.author == self.user:
            return

        input_content = message.content

        if message.author not in self.conversations:
            self.conversations[message.author] = []

        if input_content[0] == "!":
            await self.process_keyword(input_content[1:], message)
            return
        elif self.custom_sys == True:
            self.custom_sys = False
            return

        self.get_chatgpt_messages(input_content, message.author)

        async with message.channel.typing():
            try:
                response = await self.call_openai(self.conversations[message.author])
            except:
                await message.channel.send("OpenAI experienced an error generating a response. Maybe your conversation has grown too large, try `!clear_conv` to clear it, then try again. Or OpenAI may be currently overloaded with other requests. You can retry again after a short wait.")
            else:
                assistant_response = response['choices'][0]['message']['content']

                self.conversations[message.author].append(
                    {'role': 'assistant', 'content': assistant_response})

                chunk_length = 2000
                if len(assistant_response) > chunk_length:

                    await message.channel.send("Sorry for the wait, OpenAI response is large.\n Response greater than 2000 characters, sending response in chunks.\n")
                    await self.send_chunks(assistant_response, chunk_length, message)
                else:
                    await message.channel.send(assistant_response)
                
client = ChatBot(intents=intents)
client.run(DISCORD_TOKEN)
