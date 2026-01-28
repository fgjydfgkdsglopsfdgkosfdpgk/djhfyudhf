const { buildAutoReply } = require("../handlers/messages");

const sampleData = {
  admins: [],
  settings: {
    language: "ru",
    ownerId: "1234567890"
  },
  notes: [
    {
      tag: "usebot",
      responses: {
        ru: {
          patterns: ["как пользоваться ботом", "как бот работает", "где взять бота"],
          answer: "Чтобы пользоваться ботом, добавьте его на сервер и используйте команды из /notes.",
          shortAnswer: "Добавьте бота и используйте #notes."
        },
        en: {
          patterns: ["how to use the bot", "how does the bot work"],
          answer: "To use the bot, invite it to your server and check #notes for commands.",
          shortAnswer: "Invite the bot and check #notes."
        }
      }
    },
    {
      tag: "invite",
      responses: {
        ru: {
          patterns: ["где его взять", "где взять бота"],
          answer: "Бота можно взять по ссылке приглашения от админов сервера.",
          shortAnswer: "Ссылку на приглашение даст админ."
        }
      }
    }
  ]
};

const tests = [
  {
    input: "Как пользоваться ботом?",
    expected: "Чтобы пользоваться ботом"
  },
  {
    input: "Подскажи как мне им пользоваться",
    expected: "Чтобы пользоваться ботом"
  },
  {
    input: "Где взять бота и как он работает?",
    expected: "Ссылку на приглашение"
  },
  {
    input: "Как ползоваться бтотом?",
    expected: "Чтобы пользоваться ботом"
  },
  {
    input: "Как палзаватся ботом?",
    expected: "Чтобы пользоваться ботом"
  },
  {
    input: "Hello, how does the bot work",
    lang: "en",
    expected: "To use the bot"
  }
];

const run = () => {
  let passed = 0;
  for (const test of tests) {
    if (test.lang) {
      sampleData.settings.language = test.lang;
    } else {
      sampleData.settings.language = "ru";
    }
    const reply = buildAutoReply(test.input, sampleData);
    if (reply && reply.includes(test.expected)) {
      passed += 1;
      console.log(`PASS: ${test.input}`);
    } else {
      console.log(`FAIL: ${test.input}`);
      console.log(`  Reply: ${reply}`);
    }
  }
  console.log(`Passed ${passed}/${tests.length} tests`);
};

run();
