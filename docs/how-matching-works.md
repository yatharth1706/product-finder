# How Product Finder finds the same thing in other shops

*Explained as if you were five.*

## The game

Imagine you have a toy car. You love it, and you want to know if other shops
have **exactly the same** toy car.

Not a car that looks a bit like it. Not the same car in a different colour.
**The very same one.**

That is what Product Finder does. You show it a toy from the Amazon shop, and
it goes looking in the other shops.

## Step 1: Look closely at your toy

First, we look at the toy you showed us and write down what makes it special.
We call these its **stickers**.

Every toy has two stickers:

- 🏷️ **Who made it** (the brand): *Samsung*, *Nike*, *Puma*
- 🏷️ **What it is called** (the model): *Galaxy S25 Ultra*, *Air Max Bia*

And some toys have extra stickers:

| Toy | Extra stickers |
|---|---|
| 📱 Phone | How much it can remember (RAM) and how much it can hold (storage) |
| 📺 TV | How big the screen is |
| 👟 Sneakers | What colour they are |
| 👕 T-shirt | What colour it is |

## Step 2: Go to the other shops

Then we visit the right shops, all at the same time, like sending a friend to
each shop:

- Phones and TVs: **Flipkart** and **Croma**
- Sneakers and T-shirts: **Flipkart** and **Myntra**

In each shop we ask: *"Show me things like this!"* The shop gives us a pile of
toys that look similar.

## Step 3: Check every sticker

Now the important part. We pick up each toy from the pile and check **every
sticker**, one by one.

> ✅ Same maker? ✅ Same name? ✅ Same extra stickers?
> **Then it is the same toy!**
>
> ❌ Even one sticker different? **Then it is not our toy.** Put it back.

Here are some toys we put back:

- 📱 A Galaxy S25 Ultra that holds **512** things when ours holds **256**.
  *It looks the same, but it is a bigger one.*
- 📱 A Galaxy **S24** Ultra when ours is an **S25** Ultra.
  *Different number, different toy.*
- 📱 A Nord CE6 **Lite** when ours is a Nord CE6.
  *That extra word "Lite" makes it a different toy.*
- 👟 Air Max Bia shoes for **girls** when ours are for **boys**.
- 👟 Air Max Bia shoes that are **white and green** when ours are
  **white and black**.

And one very important rule:

> 🙈 **If a sticker is missing, we do not guess.**
> If we can't see the colour, we don't pretend it matches. We go and look at
> the toy's own page. If it still isn't there, the toy doesn't count.

## Step 4: Shops write things differently

Shops are a bit silly. They write the same thing in different ways:

| One shop says | Another shop says | Same? |
|---|---|---|
| 12GB | 12 GB | ✅ Yes, just spaces |
| OnePlus | One Plus | ✅ Yes |
| Titanium Grey | Titanium Gray | ✅ Yes, two spellings |
| Desert Dust | Beige | ✅ Yes, both are a sandy colour |
| 138 cm | 55 inch | ✅ Yes, same size in different rulers |
| Galaxy S25 Ultra 5G AI Smartphone | S25 Ultra | ✅ Yes, the extra words are just decoration |

So before checking stickers, we **tidy up the words**. We write sizes the same
way, turn fancy colour names into simple colours, and drop decoration words
like "5G" or "Smartphone".

We are careful not to tidy away the important bits. "Pro", "Ultra", "Lite" and
numbers like "24" or "25" always stay, because they make a toy different.

## Step 5: TVs have a secret code

Lots of TVs have the same name, like *"Crystal 4K"*, but come in different
sizes and years. So for TVs we check their **secret code**, the model number
printed on the box, like `UA55M2EHAULXL`.

The code must be **exactly** the same. `UA55UE85AHULXL` and `UA55UE83AHULXL`
look almost the same, but they are different TVs, so we put that one back.

## Step 6: Can you buy it?

When we find the same toy, we check if the shop can sell it to you **right
now**.

- 🟢 **In stock**: *"Yes! You can buy it."* We show you where.
- 🟠 **Out of stock**: *"The shop has it, but it's all sold out right now."*
  We still show you where.
- ⚪ **Not listed**: *"We looked through the whole pile, and this shop doesn't
  have your toy."*

If a shop has the same toy in a few places, we show you one you can buy, if
there is one.

## Step 7: When a shop won't talk to us

Sometimes a shop closes its door and won't let us look inside. Croma does this.

When that happens, we **don't** say "they don't have it", because we never
got to look! We say:

- 🔴 **Could not check**: *"The shop wouldn't let us in, so we don't know."*

Saying "I don't know" is better than guessing wrong.

## The whole thing in one breath

> We look at your toy's stickers. We ask other shops for similar toys. We
> tidy up the words so shops can be compared. We check every sticker, and if
> even one is different or missing, it's not your toy. Then we check if you
> can buy it, and we tell you honestly, even when the answer is "we couldn't
> look".

---

### For grown-ups

The detailed rules are in [SPEC.md](../SPEC.md#matching-rules) and in the code:

- `backend/app/matching/normalizer.py`: tidying up words, sizes and colours
- `backend/app/matching/matcher.py`: checking every sticker and explaining why
  a listing was rejected
- `backend/app/orchestrator.py`: visiting the shops at the same time and
  picking the result

A few more details:

- **Fuzzy matching only helps a little.** It gives small spelling differences
  in model names a bit of slack (RapidFuzz similarity of at least 92), but only
  after numbers and words like "Pro" or "Ultra" already match exactly.
- **A high score never wins on its own.** The match score only ranks listings
  that already passed every check.
