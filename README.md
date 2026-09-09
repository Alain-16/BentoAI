# Bento AI can be accessed here: http://66.94.114.213:3000/

# Bento AI Shopping Platform — User Documentation

## Table of Contents

1. [What Bento AI Is](#1-what-bento-ai-is)
2. [The Problem Bento AI Solves](#2-the-problem-bento-ai-solves)
3. [Who Bento AI Is For](#3-who-bento-ai-is-for)
4. [What Bento AI Can and Cannot Do](#4-what-bento-ai-can-and-cannot-do)
5. [How Bento AI Works](#5-how-bento-ai-works)
6. [How Products Are Found and Evaluated](#6-how-products-are-found-and-evaluated)
7. [Getting Started](#7-getting-started)
8. [Using the Shopping Mission Workspace](#8-using-the-shopping-mission-workspace)
9. [How Recommendations and Comparisons Work](#9-how-recommendations-and-comparisons-work)
10. [How the Smart Basket Works](#10-how-the-smart-basket-works)
11. [Changing Your Shopping Mission](#11-changing-your-shopping-mission)
12. [From Recommendation to Purchase](#12-from-recommendation-to-purchase)
13. [Real-World Examples](#13-real-world-examples)
14. [Understanding Limits and Trade-Offs](#14-understanding-limits-and-trade-offs)
15. [Common Questions and Troubleshooting](#15-common-questions-and-troubleshooting)

---

# 1. What Bento AI Is

Bento AI is a **goal-driven AI shopping platform**.

Instead of requiring you to search for every individual product yourself, Bento AI starts with what you are trying to accomplish.

For example:

> Build me a compact home gym under $1,200 CAD.

From that goal, Bento AI can help you:

- understand what products you may need
- organize those products into a shopping plan
- search across supported online stores
- compare suitable products
- consider your budget and preferences
- recommend a complete combination of products
- show alternatives so you can make the final choice
- organize selected products into one shopping basket

Bento AI is designed for situations where you know **what you want to achieve**, but you may not know exactly which products you should buy.

---

# 2. The Problem Bento AI Solves

Online shopping becomes difficult when one goal requires several products.

A normal shopping process often looks like this:

```text
Idea
  ↓
Search product
  ↓
Open many tabs
  ↓
Compare prices
  ↓
Read specifications
  ↓
Check reviews
  ↓
Search another product
  ↓
Check whether everything fits the budget
  ↓
Repeat
```

The customer has to do most of the planning and comparison manually.

Bento AI changes the workflow to:

```text
Your Goal
   ↓
Shopping Plan
   ↓
Product Discovery
   ↓
Product Evaluation
   ↓
Recommended Options
   ↓
Your Final Choice
```

The value is not simply finding a product.

The value is helping you build a **complete shopping solution**.

---

# 3. Who Bento AI Is For

Bento AI is useful for shoppers who:

- have a goal but are unsure which products are needed
- need several related products
- want to stay within a total budget
- want help comparing many options
- want product suggestions based on preferences or constraints
- do not want to spend hours researching across many stores

Typical shopping missions include:

- setting up a home office
- building a home gym
- preparing for a camping trip
- furnishing a kitchen
- buying a beginner photography setup
- creating a gaming setup
- preparing for travel
- assembling a skincare routine
- furnishing a new apartment

Bento AI can also help with simpler shopping requests, but its strongest value is in **multi-product shopping missions**.

---

# 4. What Bento AI Can and Cannot Do

## What Bento AI Can Do

Bento AI can help:

- understand a natural-language shopping goal
- identify important shopping requirements
- take a budget into account
- consider preferences and restrictions
- discover products from supported commerce sources
- compare products
- explain strengths and trade-offs
- recommend a balanced combination
- show alternatives
- update recommendations when your priorities change
- organize selected products into a smart basket

## What Bento AI Does Not Guarantee

Bento AI does not guarantee that:

- every online store in the world is searchable
- every product on the internet is available through the platform
- product prices will never change
- a product will remain in stock
- every merchant supports the same checkout experience
- the highest-rated product is always the best product for your situation
- the AI will replace your final purchasing decision

You remain in control of what you choose to buy.

---

# 5. How Bento AI Works

The central idea in Bento AI is the **Shopping Mission**.

A Shopping Mission represents what you are trying to achieve.

Example:

```text
Mission:
Build a home gym

Budget:
$1,200 CAD

Location:
Vancouver

Preferences:
Strength training
Small apartment

Important requirements:
Dumbbells
Bench
Exercise mat
Resistance bands
```

The system then works through several stages.

```text
Your Goal
   ↓
Understand the Mission
   ↓
Create Requirements
   ↓
Find Products
   ↓
Evaluate Products
   ↓
Build Comparisons
   ↓
Recommend a Basket
   ↓
You Choose
```

You do not need to understand the technical system behind these stages.

What matters is that Bento AI separates **understanding your goal**, **finding products**, and **comparing products** instead of treating every shopping problem as a simple keyword search.

---

# 6. How Products Are Found and Evaluated

One of the most important parts of Bento AI is how product recommendations are created.

The system does not simply ask an AI model to invent product recommendations.

Product selection happens in several steps.

## Step 1 — Understand the Requirement

Suppose your mission is:

> Build me a home gym under $1,200 CAD.

Bento AI may identify a requirement such as:

```text
Adjustable dumbbells
```

It also understands the context:

```text
Small apartment
Strength training
Total budget of $1,200 CAD
Location in Canada
```

This helps the system search for products that are relevant to the actual mission.

## Step 2 — Search Supported Commerce Sources

Bento AI searches supported product catalogs and commerce providers.

The platform is designed to work across multiple ecommerce sources rather than being tied to one online store.

Depending on what is available, product discovery may use:

- supported global product catalogs
- UCP-compatible merchants
- supported commerce providers
- future merchant integrations

The goal is to search real merchant product information rather than rely on products generated from AI memory.

## Step 3 — Remove Products That Clearly Do Not Fit

Products can be rejected before they reach the comparison stage.

Examples include:

- wrong currency
- unavailable product
- product outside a hard price limit
- wrong required size
- missing required feature
- product that does not satisfy an important requirement

This helps reduce irrelevant recommendations.

## Step 4 — Evaluate the Remaining Products

The remaining products are evaluated against the shopping mission.

The system can consider factors such as:

- how well the product matches the requirement
- price and value
- product quality signals
- customer preferences
- availability
- important product attributes
- trade-offs

For example, two training shoes might both be suitable, but:

```text
Product A
- cheaper
- strong requirement match
- fewer premium features

Product B
- more expensive
- stronger quality signals
- better for a specific training style
```

Bento AI uses these differences to produce useful comparisons rather than simply showing many similar products.

## Step 5 — Build a Small Comparison Set

The system does not need to show you every product it considered.

If 30 products were reviewed for one requirement, Bento AI may present only a few strong options.

For example:

```text
Training Shoes

Recommended
Reebok Nano

Alternative
Nike Metcon

Alternative
Nike Air Max Alpha Trainer
```

The purpose is to make the choice manageable.

The options should represent meaningful differences such as:

- stronger overall fit
- lower price
- different quality level
- different product strengths
- different trade-offs

## Step 6 — Consider the Whole Mission Budget

Bento AI does not only ask:

> What is the best shoe?

It also asks:

> What combination of products makes sense for the whole mission?

A product may score very highly but consume too much of the budget.

For example:

```text
Budget: $500

Shoes             $200
Shirt             $100
Shorts            $130
Water bottle       $90

Total             $520
```

The system may recommend a slightly cheaper alternative so that all required products still fit within the total budget.

This is one of the reasons Bento AI evaluates a **complete shopping solution**, not only individual products.

---

# 7. Getting Started

Using Bento AI should begin with a simple description of what you want.

## Step 1 — Describe Your Goal

Examples:

> Build me a home gym under $1,200.

> Set up my home office for less than $2,000.

> I need everything for a three-day winter camping trip.

> Furnish my kitchen for $800.

You do not need to know exact product names.

## Step 2 — Add Important Constraints

Useful information includes:

- total budget
- location
- preferred brands
- brands to avoid
- sizes
- space limitations
- quality preference
- style preference
- required features
- delivery restrictions

Example:

> Build me a home gym under $1,200 CAD. I live in Vancouver, have limited space, and mainly want strength training.

The more important context you provide, the better the system can shape the mission.

## Step 3 — Review the Shopping Plan

Bento AI creates a plan.

Example:

```text
Home Gym Plan

Required
✓ Adjustable dumbbells
✓ Adjustable bench
✓ Exercise mat
✓ Resistance bands

Optional
○ Pull-up bar
```

Review the plan before relying on the recommendations.

If something important is missing, change the mission.

## Step 4 — Review Recommended Products

For each requirement, Bento AI shows a small number of products.

You can compare:

- price
- fit with your requirement
- quality signals
- important features
- trade-offs
- merchant
- availability

## Step 5 — Choose the Products You Prefer

Bento AI can recommend a default combination, but the final choice belongs to you.

You may:

- keep the recommended product
- select an alternative
- ask for cheaper choices
- ask for higher-quality choices
- remove a requirement
- change the budget
- change a preference

---

# 8. Using the Shopping Mission Workspace

Bento AI is designed as a **Shopping Mission Workspace**, not a traditional chatbot.

The workspace should help you see the current state of your shopping goal.

A mission may contain:

```text
Mission Goal
Budget
Requirements
Recommended Products
Comparison Options
Smart Basket
Remaining Budget
Shopping Progress
```

Example:

```text
HOME GYM                              $935 / $1,200

Goal:
Small-space strength training

Shopping Plan
✓ Dumbbells
✓ Bench
✓ Exercise mat
✓ Resistance bands

Smart Basket
4 selected products

Remaining Budget
$265

Ask or change anything:
"Find me a cheaper bench"
```

The conversation box is mainly a way to **change the mission**.

It is not the main product.

---

# 9. How Recommendations and Comparisons Work

For each requirement, Bento AI may show:

## Recommended Option

The product that currently provides the strongest fit within the complete mission.

## Alternative Options

Other good products that may offer a different trade-off.

For example:

```text
TRAINING SHOES

OUR PICK
Reebok Nano
$119.99

Why:
Strong training fit and good value.

Alternative
Nike Metcon
$177

Why:
Strong lifting-focused design.

Trade-off:
Higher price.

Alternative
Nike Air Max Alpha Trainer
$125

Why:
Good value and stable gym-training design.

Trade-off:
Less specific to demanding functional training.
```

The point of comparison is not to tell you that one product is universally better.

It is to help you understand:

> Why might I choose one over the others?

---

# 10. How the Smart Basket Works

The **Smart Basket** is Bento AI's representation of the complete solution.

Example:

```text
SMART BASKET

Training Shirt       Merchant A      $47
Training Shorts      Merchant B      $54
Training Shoes       Merchant C     $119.99

Total                               $220.99
Remaining Budget                     $79.01
```

The Smart Basket may contain products from different merchants.

This is different from a normal online-store cart.

A traditional store cart usually belongs to one merchant.

The Bento AI Smart Basket represents your complete shopping mission across supported merchants.

## Prices Can Change

Product prices and availability can change after recommendations are created.

Because of this, Bento AI may refresh product information before showing or purchasing the basket.

If something changes, the system may tell you:

```text
Prices have changed since this basket was created.
The basket is now $15 over budget.
```

or:

```text
The selected shoes are no longer available.
Rebuild the basket to find a replacement.
```

This is intentional.

It is better to show the current situation than silently rely on an outdated price.

---

# 11. Changing Your Shopping Mission

You can change the mission using natural language.

Example:

> Remove the pull-up bar and spend more on the dumbbells.

Bento AI interprets this as changes to the current mission.

The system may then:

1. remove the pull-up bar requirement
2. increase the importance or budget available for dumbbells
3. re-evaluate affected products
4. rebuild the recommended basket
5. update the workspace

Other examples:

> Make the whole setup cheaper.

> I don't want Nike products.

> Replace the bench with something foldable.

> Prioritize quality over price.

> Keep everything under $900.

> I changed my shoe size to 10.

The expected result is a **visible update to your shopping mission**, not only a text response.

---

# 12. From Recommendation to Purchase

The recommendation stage and the purchase stage are separate.

The general flow is:

```text
Recommended Products
       ↓
You Review
       ↓
You Choose
       ↓
Smart Basket
       ↓
Product Information Rechecked
       ↓
Merchant Cart / Checkout
       ↓
Purchase
```

Before checkout, product details such as price and availability should be checked again.

The system may need to create separate merchant carts if the Smart Basket contains products from different stores.

Bento AI does not treat an AI recommendation as permission to purchase automatically.

The customer remains responsible for approving the purchase.

---

# 13. Real-World Examples

## Example 1 — Home Gym

You enter:

> Build me a home gym under $1,200 CAD. Small apartment. Mostly strength training.

Bento AI creates:

```text
Required
- Adjustable dumbbells
- Adjustable bench
- Exercise mat
- Resistance bands

Optional
- Pull-up bar
```

The system finds products, compares them, and creates a basket.

You then say:

> Remove the pull-up bar and improve the dumbbells.

The system adjusts the mission and produces a new basket.

## Example 2 — Home Office

You enter:

> Build me a professional home office under $2,000. I already have a laptop.

Possible shopping plan:

```text
Required
- Monitor
- Desk
- Ergonomic chair
- Keyboard
- Mouse
- Laptop dock

Optional
- Desk lamp
- Cable management
```

The system compares products across each requirement while trying to keep the complete setup within budget.

## Example 3 — Winter Camping

You enter:

> I need everything for a three-day winter camping trip.

The shopping plan may include:

```text
Tent
Sleeping bag
Sleeping pad
Cooking system
Headlamp
Water storage
Insulated clothing
Emergency equipment
```

You can then add:

> Keep everything under $1,500 and prioritize warmth over weight.

Bento AI updates the mission accordingly.

---

# 14. Understanding Limits and Trade-Offs

Bento AI is designed to make shopping easier, but recommendations should still be treated as decision support.

## Product Availability

Products can disappear, sell out, or change variants.

## Prices

Prices can change between recommendation and checkout.

## Product Information

The quality of a recommendation depends partly on the product information supplied by merchants.

If important information is missing, Bento AI may:

- reduce the product's match score
- show the missing information as a trade-off
- prefer another product with stronger evidence

For example:

```text
Trade-off:
Medium size availability is not confirmed.
```

This is more trustworthy than pretending the information is known.

## Quality Is Not Based on One Signal

A product recommendation should not depend only on star ratings.

Bento AI may consider several signals together, such as:

```text
requirement match
price/value
quality indicators
ratings where available
preference match
availability
product attributes
known trade-offs
```

A product with the highest review count may still be a worse fit for your mission.

## AI Can Make Mistakes

AI helps interpret your goal and product information, but it should not be treated as an infallible authority.

For important purchases, review:

- merchant information
- product specifications
- sizes
- warranty
- delivery terms
- return policy
- final checkout details

before buying.

---

# 15. Common Questions and Troubleshooting

## Why did Bento AI choose a cheaper product instead of the highest-scoring one?

Because the system considers the **whole mission budget**.

A slightly cheaper product may allow the complete set of required products to fit within your budget.

## Why are only a few products shown when many were considered?

The platform intentionally reduces large search results into a smaller comparison set.

Showing 30 nearly identical products would move the research burden back to you.

The goal is to present a few meaningful choices.

## Why do two recommended products look similar?

Sometimes the strongest available products are similar.

The platform attempts to provide useful alternatives, but available catalog results may limit how different those alternatives can be.

## Why did a product disappear from my basket?

The product may:

- no longer be available
- no longer have a purchasable offer
- fail a fresh lookup
- become unavailable in your location

Bento AI may ask you to rebuild that part of the basket.

## Why did my basket total change?

Online prices can change.

Bento AI may refresh prices after a basket has already been created.

If the new total exceeds your budget, the system should clearly tell you.

## Why was a product rejected?

Possible reasons include:

- currency mismatch
- unavailable product
- price outside the allowed range
- wrong size
- missing required feature
- weak requirement match
- unsupported destination

## Can I change the recommendations?

Yes.

Examples:

> Make it cheaper.

> Give me premium options.

> Avoid this brand.

> Replace this product.

> Remove this requirement.

> Increase my budget to $1,500.

The system should update the mission and affected recommendations.

## Does Bento AI buy products automatically?

Not by default.

The system can help prepare the shopping basket and commerce workflow, but you remain responsible for approving what you want to buy.

## Is Bento AI limited to Shopify?

No.

The platform is designed to support multiple ecommerce providers.

Shopify-compatible catalog infrastructure may be one discovery source, but the product architecture is designed around broader commerce interoperability and supported merchant integrations.

---

# Final Mental Model

The easiest way to understand Bento AI is:

```text
Tell Bento AI what you want to accomplish
                ↓
Bento AI creates the shopping plan
                ↓
It finds real products from supported stores
                ↓
It removes weak or unsuitable options
                ↓
It compares the strongest candidates
                ↓
It balances the complete solution against your budget
                ↓
You review and choose the products
                ↓
The Smart Basket organizes your shopping mission
                ↓
You proceed toward merchant checkout
```

The customer provides the **goal**.

Bento AI handles much of the **shopping research and organization**.

The customer keeps control of the **final decision**.
