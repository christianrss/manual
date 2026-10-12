---
id: c-pointers-arrays-object-lifetimes
title: "C programming foundations: pointers, arrays, bounds and object lifetimes"
description: "Learn C pointers, array decay, valid pointer arithmetic, ownership and lifetime through a bounded C11 program and tests."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [data-types-bytes-and-representation, program-memory-references-lifetimes]
sources:
  - {title: "C language — pointer declaration", url: "https://en.cppreference.com/w/c/language/pointer", kind: "C language reference"}
  - {title: "C language — pointer arithmetic", url: "https://en.cppreference.com/w/c/language/operator_arithmetic", kind: "C language reference"}
  - {title: "C language — object lifetime", url: "https://en.cppreference.com/w/c/language/lifetime", kind: "C language reference"}
  - {title: "C language — storage duration", url: "https://en.cppreference.com/w/c/language/storage_duration", kind: "C language reference"}
---
Python's object references are useful for reasoning about aliasing, but systems programmers must also know how C exposes **addresses, arrays, indirection and object lifetimes**. These concepts explain both high-performance data access and entire classes of memory-safety errors. The goal is not to memorize dangerous tricks; it is to define the valid operations before considering manual allocation or optimization [1][2].

## Objects, addresses and pointer types

An object occupies storage over a defined lifetime. The address-of operator obtains a pointer to a suitable object, while the unary indirection operator accesses an object through a valid pointer. In a declaration such as an integer pointer p initialized with the address of a local integer x, p has pointer type and *p designates x. Assigning to *p changes x, not p itself [1].

A pointer value is not an untyped integer address. It has a referenced type that influences valid dereference and pointer arithmetic. In C, null pointers do not designate an object and must not be dereferenced. A pointer that designated an object whose lifetime has ended is not rescued by the fact that memory still appears to contain the old bytes. Such access has undefined behavior [3].

The distinction between a pointer and its referent is parallel to, but more explicit than, the distinction between a Python name and its object. C permits direct operations on object storage; Python's name bindings do not provide equivalent portable pointer arithmetic.

## Arrays are not identical to pointers

An array declaration of four integers creates a contiguous aggregate containing four integer objects. In most expression contexts, an array expression is converted to a pointer to its first element. This is why passing an array to a function declared with an integer pointer parameter works. However, an array is **not itself a pointer variable**: its storage and type are different [1].

For a local array, applying sizeof to the entire array returns its full byte extent; applying sizeof to a pointer returns the size of the pointer object. Dividing sizeof array by sizeof array[0] counts elements only while the compiler still sees that array expression, not after it has decayed in a function parameter. A function that receives a pointer must therefore receive the count or another valid bound separately.

Two-dimensional arrays need additional care: an array of rows does not automatically convert to an int**. Its first element is itself an array, and pointer-to-row arithmetic advances by whole rows. Confusing these types can make indexing invalid even when the memory appears contiguous.

## Pointer arithmetic and one-past-the-end

For an array of N elements, a pointer to element i may be advanced within the range of elements or to the position **one past the last element**. A one-past pointer can be formed, compared or subtracted against pointers into the same array under the relevant rules, but it must not be dereferenced. Forming a pointer before the first element or farther than one past is not merely a safe pointer that should not be accessed: the arithmetic itself can already be undefined [2].

Adding one to an int pointer advances by the size of an int element, not by one byte. Subtracting two pointers within the same array produces an element distance of type ptrdiff_t, not a count of raw bytes. Pointer arithmetic between unrelated independently allocated objects is not an ordinary way to compare their memory positions.

The code example computes the one-past pointer for a four-element array, subtracts it from the first pointer and dereferences only valid in-range positions. It never dereferences the one-past pointer.

## A bounded function with an explicit contract

Suppose a function sums a sequence of nonnegative integers, where each value is at most 1000 and there are at most 1000 elements. Its input is a pointer plus a count, and its output is an independently supplied pointer. If the result pointer is null, return false. If count is nonzero but input pointer is null, return false. An empty sequence may be represented by a null input with count zero, and its sum is zero.

This contract bounds the maximum mathematical sum at one million, which fits the minimum range guaranteed for a C long long. The function validates all values before updating its caller-provided result; if it rejects an invalid element, the existing output remains unchanged. The caller is responsible for ensuring that a non-null input points to at least count valid int elements, and that a non-null output points to writable long long storage. A pointer/count API cannot discover that physical capacity by inspecting a raw pointer.

The result pointer is an example of explicit indirection: the callee writes into the caller's object through a valid address, rather than attempting to rebind a caller variable. A const-qualified input pointer states that this function must not use that pointer to modify the input values.

~~~c
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

static bool sum_bounded(const int *values, size_t count, long long *out) {
    if (out == NULL || count > 1000 || (count != 0 && values == NULL))
        return false;
    long long sum = 0;
    for (size_t i = 0; i < count; ++i) {
        if (values[i] < 0 || values[i] > 1000)
            return false;
        sum += (long long)values[i];
    }
    *out = sum;
    return true;
}

int main(void) {
    int values[4] = {3, 5, 7, 9};
    int *first = &values[0];
    int *one_past = values + 4;
    assert(*(first + 2) == 7);
    assert(one_past - first == 4);
    assert(sizeof values / sizeof values[0] == 4);

    long long total = -1;
    assert(sum_bounded(values, 4, &total) && total == 24);
    assert(!sum_bounded(NULL, 1, &total) && total == 24);
    assert(!sum_bounded(NULL, 0, NULL) && total == 24);
    assert(sum_bounded(NULL, 0, &total) && total == 0);

    int *allocated = malloc(4 * sizeof *allocated);
    if (allocated == NULL)
        return 1;
    for (size_t i = 0; i < 4; ++i)
        allocated[i] = values[i];
    assert(sum_bounded(allocated, 4, &total) && total == 24);
    free(allocated);
    allocated = NULL;
    printf("sum=%lld\n", total);
    return 0;
}
~~~

## Automatic, static and allocated storage

C distinguishes automatic, static, thread and allocated storage durations [4]. A non-static local array usually has automatic storage duration; its lifetime ends at the enclosing scope's specified boundary. Returning a pointer to such a local array and then dereferencing it in the caller is invalid because the array no longer exists. A pointer cannot extend an object's lifetime.

Calling malloc requests allocated storage; its result must be checked for null before dereferencing. For the successful allocation in the example, the buffer holds enough space for four integers because its byte size is four times sizeof one integer. Once the program has finished using the buffer, it calls free exactly once and does not use the pointer to access storage afterward. Assigning null after free is useful for that particular variable, but it cannot repair other aliases that may still retain the invalid pointer.

This is manual lifetime management: the code must document who frees memory and how failure paths release resources. Static-duration objects do not require malloc/free, but they have a different lifetime and potentially shared mutable state.

## Proof of bounded behavior and complexity

If count is at most 1000, every input value lies in [0,1000], and out refers to writable long long storage, then the sum loop adds count values whose total lies between zero and one million. The loop invariant is that at iteration i, sum equals the total of the first i validated elements. Each iteration validates the current element and updates the accumulated total. At termination, sum equals the total of the entire valid sequence. If validation fails, the function returns before writing out.

The loop visits count elements once: O(n) time for n=count and O(1) scalar auxiliary space, assuming bounded-cost integer arithmetic. The caller's input array requires O(n) storage, but that storage belongs to the caller and is not allocated by sum_bounded. Using long long prevents overflow **under the stated numeric bounds**; it does not make every possible sum safe in arbitrary C programs.

In the test program, assertions check expected behavior. Production input validation must not be placed only inside assert expressions because builds with assertions disabled can omit them. An actual test harness should call the function even when NDEBUG is defined and verify its results independently.

## Undefined behavior, sanitizers and counterexamples

C can compile a program that dereferences a one-past pointer, reads freed memory or supplies an incorrect length; compilation success is not evidence that those operations are valid. Some invalid programs appear to work on one machine, which makes testing alone insufficient. Derive the bounds and lifetimes from the contract before writing pointer arithmetic [2][3].

Compiler warnings, address sanitizers and runtime tests can catch many mistakes but cannot certify the absence of every undefined behavior. Raw pointers provide no automatic ownership tracking, and const on a particular pointer path does not make all aliases immutable. Design APIs around explicit lengths, ownership and failure rules. Prefer existing safe abstractions when direct pointer work is unnecessary.

## Exercises and verification

1. Explain the difference between the type and size of a four-element int array and a pointer to its first element.
2. Form a valid one-past pointer and explain why dereferencing it is undefined.
3. Extend the bounded sum function to reject any value above 1000 while preserving the previous output on error.
4. Write a function that returns a pointer to a local automatic array; identify why accessing the result after return is invalid, without executing undefined behavior.
5. Add a test for count zero with null input and valid output; contrast it with null output.
6. Compile the provided C11 program with warnings and sanitizers available on your platform; explain what tests can and cannot prove.

Continue with [program memory and aliasing](/en/topics/program-memory-references-lifetimes/), [data representation](/en/topics/data-types-bytes-and-representation/) and [heap allocation](/en/topics/heap-allocation-fragmentation/).