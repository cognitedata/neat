# Rules Validation

**NEAT** supports the validation of the consistency of a `Rule` object. This includes checking the `Rule` object
against previous iteration and another `Rule` object that is the basis for the current `Rule` object.

There are three fields in the `Metadata` of a `Rule` object that tells **NEAT** how to validate the `Rule` object:

* `dataModelType` - The type of data model the `Rule` object represents. This can be either `solution` or `enterprise`.
* `schema` - The schema completeness of the `Rule` object. This can be either `complete`, `extension`, or `partial`.
* `extension` - In the case of `schema=extension`, this field specifies how the `Rule` object extends the previous iteration.

There can be up to three different `Rule` objects that are used for validation. In a spreadsheet, these have
different prefixes:

* **No prefix**: The main `Rules` object often referred to as the `user` `Rules` object.
* **`Last`**: The previous iteration of the `user` `Rules` object.
* **`Ref`**: (short for Reference) A `Rules` object that is referenced by the `user` `Rules` object.

## <code>dataModelType</code>—Whether to Validate against Reference Object

If the `dataModelType` is set to `enterprise`, then the `Rule` object is expected to be a fundamental data model,
meaning that is not based on another data model. In this case, if there is a `Reference` it will be ignored.

If the `dataModelType` is set to `solution`, then the `Rule` object is expected to be based on another data model.
For example, the user rules might use classes, views, or containers from the reference rules. If the `Reference` rules
is missing an error will be raised.

## <code>schema</code>—Whether to Validate against Last Rules object

If the `schema` is set to `complete`, then the `Rule` object is expected to be a complete data model. This means that
the `Rule` object should contain all the classes, views, and containers that are needed for the data model.

If the `schema` is set to `partial`, then the `Rule` object is expected to be a partial data model. No validation
of the consistency of the `Rule` object as a whole will be done. This is useful when you develop a data model in
a team with input from multiple sources, which are later merged into a complete data model.

If the `schema` is set to `extension`, then the `Rule` object is expected to be an extension of the previous iteration.
This means that the: User Rules+Last Rules=Complete Rules. If the `Last` rules are missing an error will be raised.
How the validation is done is specified in the `extension` field.

## <code>extension</code>—How to Validate against Last Rules object

Given that the `schema=extension`, the `extension` field specifies how the `Rule` object extends the previous iteration.
This typically applies to the implementation profile of the `Rule` object, the `DMS Rules`. There are three options:

* `addition` - You are adding new properties, views, or containers to the data model. Use cases which are based on the
  previous iteration are not affected.
* `reshape` - You change the properties or views of the data model. For example, adding, removing, or renaming properties.
  Use cases which are based on the previous iteration are affected, and may need to be updated.
* `rebuild` - You change the properties, views, or containers of the data model. In addition, to use cases which are
  based on the previous iteration, may need to be updated, you will also likely need to do a data migration.

By setting this field, you will get help from **NEAT** to not accidentally cause a change do require rebuilding of
use cases or data migration.

## Examples

### Example 1: Creating an Enterprise Model from an External Source

You will set the following fields.

| Field           | Value        |
|-----------------|--------------|
| schema          | `complete`   |
| dataModelType   | `enterprise` |

In addition, you can have the external source as a `Reference` object, but it will be ignored.
The reason to have the `Reference` object is to have easy access to the classes, views, and containers
you may want to move over to the `user` `Rules` object.

### Example 2: Updating an Enterprise Model

You will set the following fields.

| Field           | Value        |
|-----------------|--------------|
| schema          | `extended`   |
| extension       | `addition`   |
| dataModelType   | `enterprise` |

In addition, you need to have a `Last` `Rules` object that is the previous iteration. In this case,
you are extending the Enterprise model, but you do not want to cause any changes to the use cases (or other models)
that are based on the previous iteration.

### Example 3: Creating a Solution Model

You will set the following fields.

| Field           | Value      |
|-----------------|------------|
| schema          | `complete` |
| dataModelType   | `solution` |

In addition, you need to have a `Reference` `Rules` object that contains the Enterprise Model.

### Example 4: Updating a Solution Model

You will set the following fields.

| Field           | Value      |
|-----------------|------------|
| schema          | `extended` |
| extension       | `rebuild`  |
| dataModelType   | `solution` |

In addition, you need to have a `Last` and a `Reference` `Rules` object. The `Last` `Rules` object is the previous
iteration of the `user` `Rules` object. The `Reference` `Rules` object is the Enterprise Model. In this case,
you are allowed to change the data model in a way that requires rebuilding of use cases or data migration.
