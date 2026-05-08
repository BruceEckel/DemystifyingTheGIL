# Preface

This book was produced while developing my 2025 Pycon presentation titled "Demystifying the GIL."
That presentation was inspired by a conversation with Python's creator,
Guido van Rossum, a year or so prior.
Guido made a comment to the effect of,
"I think people will be surprised by the side effects of working without the GIL."
Eventually I began wondering what the simplest side effects might be.
My goal for the presentation is to show how behavior changes when the GIL is removed from simple code examples,
and to explain why that happens.
This way people might be a little less surprised when these changes occur and have a sense of how to attack the problem.

The explanation turned out to be more challenging than I had anticipated.
The research generated this book.
