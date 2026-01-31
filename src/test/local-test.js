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
          patterns: ["как пользоваться ботом", "как бот работает", "как мне пользоваться", "как юзать бота"],
          answer: "Чтобы пользоваться ботом, добавьте его на сервер и используйте команды из /notes."
        }
      }
    },
    {
      tag: "invite",
      responses: {
        ru: {
          patterns: ["где взять бота", "дайте ссылку на бота", "скиньте ссылку"],
          answer: "Бота можно взять по ссылке приглашения от админов сервера."
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
    input: "Дайте ссылку на бота",
    expected: "Бота можно взять"
  },
  {
    input: "Где взять бота и как он работает?",
    expected: "Бота можно взять"
  },
  {
    input: "Как ползоваться бтотом?",
    expected: "Чтобы пользоваться ботом"
  },
  {
    input: "Как палзаватся ботом?",
    expected: "Чтобы пользоваться ботом"
  }
];

const run = () => {
  let passed = 0;
  for (const test of tests) {
    sampleData.settings.language = "ru";
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
